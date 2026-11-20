# nzdclive (NZ Domestic Cricket Live)

A GitHub Pages site that shows every stream currently live on the
[YouTube channel](https://www.youtube.com/channel/UCuKowzPg2-A0FcmyPa3yWug/streams),
tiled to fill the screen.

## How it works

- `scripts/fetch_live.py` reads the channel's public Live tab and writes
  `site/live.json` with the IDs of streams YouTube marks as live. No API key.
- `.github/workflows/pages.yml` runs that script every 5 minutes (GitHub may
  delay scheduled runs) and redeploys the site when the list changes.
- `site/index.html` re-reads `live.json` every minute, adding and removing
  players without reloading the ones already playing. Players start muted.

## Layout

Tiles are 16:9 and sized as large as the window allows: 1 fills the screen,
2 sit side by side, 3 or 4 use a 2x2 grid, and larger counts use whichever
grid gives the biggest tiles. 5 or 6 streams always use a 3x2 grid with the
videos enlarged to fill their cells and the sides trimmed (at most 25%, set by
`MAX_CROP` in `site/index.html`).

## Setup

In the repository settings, under Pages, set the source to "GitHub Actions".
