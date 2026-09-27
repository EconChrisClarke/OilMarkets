# Chart builder (repo copy)

A copy of the econ-chart-style skill's chart builder, kept here so the repo's
charts can use features the skill's copy doesn't have yet. Same usage:

```bash
python3 chartkit/scripts/build_chart.py --config charts/<name>.json --out <name>.html
```

## Differences from the skill's copy

- **Series checkboxes.** Line, area and scatter charts with more than one
  series get a "Series" row in the controls. Unticking a series removes it
  and the axes, end labels, copy buttons and PNG exports rescale to what is
  left. At least one series stays on. Colours stay with their series.
  - `hidden: ["Name"]` in the config switches a series off at load.
  - An annotation with `series: "Name"` goes when that series is off, and any
    annotation left outside the rescaled y axis is dropped.

To bring this into the skill, copy `assets/chart-template.html` over the
skill's `assets/chart-template.html` and re-upload the skill.
