# nzdclive (NZ Domestic Cricket Live)

A GitHub Pages site that shows every stream currently live on the
[YouTube channel](https://www.youtube.com/channel/UCuKowzPg2-A0FcmyPa3yWug/streams),
plus any public stream scheduled to start today (New Zealand time), tiled to
fill the screen.

## How it works

- `scripts/fetch_live.py` reads the channel's public Live tab and writes
  `site/live.json` with the streams YouTube marks as live, followed by those
  marked upcoming whose start time falls on today's NZ date (earliest first).
  The exact start time of each upcoming stream is looked up by its video ID.
  No API key.
- `.github/workflows/pages.yml` runs that script and redeploys the site when
  the list changes. GitHub's own 5-minute schedule is unreliable, so an external
  cron service also starts it every 5 minutes through the `workflow_dispatch`
  API (the token lives in that service, never in this repo).
- `site/index.html` re-reads `live.json` every minute, adding and removing
  players without reloading the ones already playing. Players start muted.
  A scheduled stream shows YouTube's waiting screen until it starts, and its
  player is reloaded once it goes live.
- Every 5 minutes the page checks each live player through YouTube's IFrame
  Player API. A player more than 15 seconds behind the live edge is moved back
  to live, and a paused one is resumed (`CHECK_MS` and `MAX_LAG_S` in
  `site/index.html`). The same check also runs whenever you switch back to
  the tab.

## Layout

Tiles are 16:9 and sized as large as the window allows: 1 fills the screen,
2 sit side by side, 3 or 4 use a 2x2 grid, and larger counts use whichever
grid gives the biggest tiles. 5 or 6 streams always use a 3x2 grid with the
videos enlarged to fill their cells and the sides trimmed (at most 25%, set by
`MAX_CROP` in `site/index.html`).

## Setup

In the repository settings, under Pages, set the source to "GitHub Actions".
