# OilMarkets: notes for Claude

## Publishing (standing instruction from Christopher)

Published charts live on GitHub Pages and are updated in place. **When he asks
for a change to a chart or map, publish it without asking:** make the change,
check every frame, commit, open the PR, squash-merge it into `main`, and verify
the live URL serves the new file before replying with the link. Don't stop at a
draft PR and wait for "publish". New charts he asks for are published the same
way unless he says otherwise.

- Live pages: `https://econchrisclarke.github.io/OilMarkets/<slug>.html`
  (HTML at the repo root; keep each slug unchanged so shared links keep working).
- Charts build with `chartkit/scripts/build_chart.py`, maps with
  `maps/build_map.js` (repo copies of the econ-chart-style builders, with
  features the skill may not have yet). Each chart's data script under
  `scripts/` writes its config; never edit built HTML by hand.
- After a merge, restart the working branch from `origin/main`; a merged PR
  is never reused.
