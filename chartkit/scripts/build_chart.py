#!/usr/bin/env python3
"""
Build a finished chart page from the house template plus a JSON config.

    python3 build_chart.py --config chart.json --out cancer-deaths.html
    python3 build_chart.py --config chart.json --out out.html --logo logo.png

Why a script instead of hand-writing the HTML: the template carries ~700 lines
of rendering engine that must not drift between charts. Regenerating it by hand
invites silent typos and slow divergence in the house style. Write only the
config; let this stamp it into a known-good template.

The config is validated before writing, because a chart that renders with
mismatched series lengths or a missing source line is worse than an error.
"""

import argparse
import base64
import json
import mimetypes
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "chart-template.html"

VALID_TYPES = {"line", "area", "column", "bar", "scatter"}
VALID_XTYPES = {"year", "date", "category", "number"}
VALID_SCALES = {"linear", "log", "sqrt"}


def fail(msg):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(1)


def validate(c):
    problems = []

    for field in ("type", "headline", "series"):
        if not c.get(field):
            problems.append("missing required field: " + field)
    if problems:
        fail("; ".join(problems))

    if c["type"] not in VALID_TYPES:
        problems.append("type must be one of %s (got %r)" % (sorted(VALID_TYPES), c["type"]))

    xtype = c.get("xType", "year")
    if xtype not in VALID_XTYPES:
        problems.append("xType must be one of %s (got %r)" % (sorted(VALID_XTYPES), xtype))

    if not c.get("source"):
        problems.append("no source given - every chart needs one, it is what makes it citable")

    cat_chart = c["type"] in ("column", "bar")
    cats = c.get("categories") or []
    if cat_chart and not cats:
        problems.append("column/bar charts need a non-empty 'categories' list")

    for i, s in enumerate(c["series"]):
        if not isinstance(s, dict) or "data" not in s:
            problems.append("series[%d] needs a 'data' array" % i)
            continue
        if len(c["series"]) > 1 and not s.get("name"):
            problems.append("series[%d] needs a 'name' (multi-series charts label by name)" % i)
        data = s["data"]
        if not data:
            problems.append("series[%d] has no data points" % i)
            continue
        if cat_chart:
            if len(data) != len(cats):
                problems.append(
                    "series[%d] has %d values but there are %d categories"
                    % (i, len(data), len(cats)))
            if any(isinstance(v, (list, tuple)) for v in data):
                problems.append(
                    "series[%d]: column/bar data is a flat list of numbers, not [x,y] pairs" % i)
        else:
            # scatter points may carry a third element: the point's own label,
            # normally the date it came from. It drives the hover text and the
            # Range control, which on a scatter cannot filter on the x axis.
            wide = 3 if c["type"] == "scatter" else 2
            bad = [j for j, p in enumerate(data)
                   if not (isinstance(p, (list, tuple)) and 2 <= len(p) <= wide)]
            if bad:
                problems.append(
                    "series[%d]: %s data must be [x, y]%s pairs (bad index %s)"
                    % (i, c["type"],
                       " or [x, y, label]" if wide == 3 else "", bad[:3]))
            elif c["type"] == "scatter":
                labelled = sum(1 for p in data if len(p) == 3)
                if labelled and labelled != len(data):
                    problems.append(
                        "series[%d]: %d of %d scatter points have a label; "
                        "label all of them or none" % (i, labelled, len(data)))
            elif xtype == "date":
                for p in data:
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(p[0])):
                        problems.append(
                            "series[%d]: xType 'date' needs YYYY-MM-DD strings (got %r)"
                            % (i, p[0]))
                        break

    # Log axes. Caught here rather than in the browser, where a non-positive
    # value becomes -Infinity and the chart renders blank with no clue why.
    cat_x = c["type"] in ("column", "bar")
    for axis in ("x", "y"):
        scale = c.get(axis + "Scale", "linear")
        if scale not in VALID_SCALES:
            problems.append("%sScale must be one of %s (got %r)"
                            % (axis, sorted(VALID_SCALES), scale))
            continue
        if scale == "linear":
            continue
        if cat_x:
            problems.append("%sScale %r does not apply to column/bar charts"
                            % (axis, scale))
            continue
        idx = 0 if axis == "x" else 1
        for i, s in enumerate(c["series"]):
            for j, p in enumerate(s.get("data") or []):
                if not isinstance(p, (list, tuple)) or len(p) <= idx:
                    continue
                v = p[idx]
                bad = (v <= 0) if scale == "log" else (v < 0)
                if isinstance(v, (int, float)) and bad:
                    problems.append(
                        "%sScale %r needs %s values: series[%d] point %d has %s=%r"
                        % (axis, scale,
                           "positive" if scale == "log" else "non-negative",
                           i, j, axis, v))
                    break

    for i, r in enumerate(c.get("rules") or []):
        if not isinstance(r, dict) or "at" not in r:
            problems.append("rules[%d] needs an 'at' value" % i)
        elif r.get("axis", "x") not in ("x", "y"):
            problems.append("rules[%d]: axis must be 'x' or 'y' (got %r)"
                            % (i, r.get("axis")))
    for i, g in enumerate(c.get("regions") or []):
        if not isinstance(g, dict):
            problems.append("regions[%d] must be an object" % i)
        elif not any(g.get(k) is not None for k in ("x0", "x1", "y0", "y1")):
            problems.append("regions[%d] needs at least one bound "
                            "(x0/x1/y0/y1)" % i)

    # Point labels are matched against each scatter point's third element, so a
    # name that is not in the data would silently never appear. Catch the typo
    # here instead of leaving a country quietly missing from the chart.
    pl = c.get("pointLabels")
    if pl and pl != "all":
        if c["type"] != "scatter":
            problems.append("pointLabels only applies to scatter charts")
        elif not isinstance(pl, list):
            problems.append("pointLabels must be a list of names, or 'all'")
        else:
            known = {str(p[2]) for s in c["series"]
                     for p in (s.get("data") or [])
                     if isinstance(p, (list, tuple)) and len(p) > 2}
            if not known:
                problems.append(
                    "pointLabels needs the points to carry a third element "
                    "(the name); none of them do")
            else:
                missing = [n for n in pl if str(n) not in known]
                if missing:
                    problems.append(
                        "pointLabels names not present in the data: %s"
                        % ", ".join(map(str, missing[:5])))

    head = c.get("headline", "")
    if len(head) > 110:
        problems.append("headline is %d characters; over ~110 it wraps to four lines "
                        "on a phone and crowds the plot" % len(head))

    if problems:
        fail("\n       ".join(problems))

    warnings = []
    if head and head.rstrip().endswith("."):
        warnings.append("headline ends with a period - house style drops it")
    if len(c["series"]) > 6:
        warnings.append("%d series: past ~6 lines a reader cannot track them; "
                        "consider small multiples or highlighting one"
                        % len(c["series"]))
    for w in warnings:
        print("note: " + w, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="JSON config file")
    ap.add_argument("--out", required=True, help="output .html path")
    ap.add_argument("--logo", help="image file to embed in the footer")
    ap.add_argument("--template", default=str(TEMPLATE))
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        fail("config not found: " + str(cfg_path))
    try:
        # utf-8-sig, not utf-8: editors and PowerShell on Windows write a BOM,
        # and plain utf-8 rejects it with a message that sounds like the JSON
        # is malformed when it is fine.
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        fail("config is not valid JSON: %s (line %d)" % (e.msg, e.lineno))

    validate(cfg)

    if args.logo:
        lp = Path(args.logo)
        if not lp.exists():
            fail("logo not found: " + str(lp))
        mime = mimetypes.guess_type(lp.name)[0] or "image/png"
        cfg["logo"] = "data:%s;base64,%s" % (
            mime, base64.b64encode(lp.read_bytes()).decode("ascii"))

    tpl = Path(args.template).read_text(encoding="utf-8")
    block = "/* CHART_CONFIG_START */\nconst CHART = %s;\n/* CHART_CONFIG_END */" % (
        json.dumps(cfg, indent=2, ensure_ascii=False))

    new, n = re.subn(
        r"/\* CHART_CONFIG_START \*/.*?/\* CHART_CONFIG_END \*/",
        lambda _m: block, tpl, flags=re.S)
    if n != 1:
        fail("could not find the config markers in the template")

    new = new.replace("<title>CHART_TITLE</title>",
                      "<title>%s</title>" % cfg["headline"].replace("<", "&lt;"))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(new, encoding="utf-8")

    pts = sum(len(s["data"]) for s in cfg["series"])
    print("wrote %s  (%s, %d series, %d points, %.0f KB)"
          % (out, cfg["type"], len(cfg["series"]), pts, out.stat().st_size / 1024))


if __name__ == "__main__":
    main()
