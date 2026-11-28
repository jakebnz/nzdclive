(() => {
  "use strict";
  // Per-page settings come from the <script> tag that loads this file:
  //   data-mode    "cropped" (3x2 grid with sides trimmed for 5-6 streams) or "grid" (never crops)
  //   data-filter  only show streams whose title contains this word (case-insensitive)
  //   data-base    path from the page to the site root, where live.json lives
  const CFG = document.currentScript.dataset;
  const CROPPED = CFG.mode === "cropped";
  const BASE = CFG.base || "";
  const FILTER = CFG.filter
    ? new RegExp("\\b" + CFG.filter.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i")
    : null;
  const ASPECT = 16 / 9;
  // For 5 or 6 streams a 3x2 grid is used and each video is scaled up to fill
  // its cell height, trimming the sides. This caps how much width may be cut
  // (0.25 = up to a quarter); any remaining gap shows as thin bars top and bottom.
  const MAX_CROP = 0.25;
  const POLL_MS = 60 * 1000;
  const ID_RE = /^[A-Za-z0-9_-]{11}$/;
  // Keep every live player at the live edge: every CHECK_MS, a player that has
  // fallen more than MAX_LAG_S seconds behind is moved back to live, and a
  // paused player is resumed.
  const CHECK_MS = 5 * 60 * 1000;
  const MAX_LAG_S = 15;

  const grid = document.getElementById("grid");
  const empty = document.getElementById("empty");
  const emptyMsg = document.getElementById("empty-msg");
  const tiles = new Map(); // video id -> tile element (kept so players don't reload)
  const players = new Map(); // video id -> YT.Player controlling that tile's iframe

  // Pick columns/rows so 16:9 tiles are as large as possible.
  function layout(n, W, H) {
    if (CROPPED && (n === 5 || n === 6)) {
      const cellW = W / 3, cellH = H / 2;
      let vw = cellH * ASPECT;
      if (vw > cellW) vw = Math.min(vw, cellW / (1 - MAX_CROP));
      else vw = cellW; // wide viewport: no crop needed
      return { cols: 3, cellW, cellH, vw, vh: vw / ASPECT };
    }
    let best = null;
    for (let cols = 1; cols <= n; cols++) {
      const rows = Math.ceil(n / cols);
      const w = Math.min(W / cols, (H / rows) * ASPECT);
      // Prefer the larger tile; on a tie, prefer fewer rows (side by side).
      if (!best || w >= best.w - 0.5) best = { cols, w };
    }
    const vw = best.w, vh = vw / ASPECT;
    return { cols: best.cols, cellW: vw, cellH: vh, vw, vh };
  }

  function render() {
    const n = tiles.size;
    empty.style.display = n ? "none" : "grid";
    if (!n) return;
    const W = window.innerWidth, H = window.innerHeight;
    const L = layout(n, W, H);
    // Floor to whole pixels so rounding never pushes a tile onto a new row.
    const cw = Math.floor(L.cellW), ch = Math.floor(L.cellH);
    grid.style.width = (cw * L.cols) + "px";
    grid.style.left = ((W - cw * L.cols) / 2) + "px";
    grid.style.right = "auto";
    for (const tile of tiles.values()) {
      tile.style.width = cw + "px";
      tile.style.height = ch + "px";
      const f = tile.firstChild;
      f.style.width = Math.ceil(L.vw) + "px";
      f.style.height = Math.ceil(L.vh) + "px";
    }
  }

  function makeTile(v) {
    const tile = document.createElement("div");
    tile.className = "tile";
    const f = document.createElement("iframe");
    const params = new URLSearchParams({
      autoplay: "1", mute: "1", playsinline: "1", rel: "0",
      enablejsapi: "1", origin: location.origin,
    });
    f.src = "https://www.youtube-nocookie.com/embed/" + v.id + "?" + params;
    f.title = typeof v.title === "string" && v.title ? v.title : "Live stream";
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.referrerPolicy = "strict-origin-when-cross-origin";
    tile.appendChild(f);
    return tile;
  }

  // YouTube's IFrame Player API lets the page read and move each player's
  // position. If it fails to load, the players still work, just without this.
  let apiReady = false;
  window.onYouTubeIframeAPIReady = () => {
    apiReady = true;
    for (const [id, tile] of tiles) attachPlayer(id, tile);
  };
  const apiScript = document.createElement("script");
  apiScript.src = "https://www.youtube.com/iframe_api";
  document.head.appendChild(apiScript);

  function attachPlayer(id, tile) {
    if (!apiReady || players.has(id)) return;
    try {
      players.set(id, new YT.Player(tile.firstChild));
    } catch (e) { /* leave this player unmanaged */ }
  }

  function detachPlayer(id) {
    const p = players.get(id);
    players.delete(id);
    try { if (p) p.destroy(); } catch (e) { /* already gone */ }
  }

  function keepLive() {
    for (const [id, p] of players) {
      const tile = tiles.get(id);
      if (!tile || tile.dataset.status !== "live" || typeof p.getPlayerState !== "function") continue;
      try {
        const state = p.getPlayerState();
        if (state === YT.PlayerState.ENDED) continue; // the broadcast has finished
        const edge = p.getDuration(), now = p.getCurrentTime();
        if (state === YT.PlayerState.PAUSED) p.playVideo();
        if (edge > 0 && edge - now > MAX_LAG_S) p.seekTo(edge, true);
      } catch (e) { /* player not ready yet */ }
    }
  }

  function update(list) {
    const wanted = list.filter(v => v && typeof v.id === "string" && ID_RE.test(v.id) &&
      (!FILTER || (typeof v.title === "string" && FILTER.test(v.title))));
    const ids = new Set(wanted.map(v => v.id));
    for (const [id, tile] of tiles) {
      if (!ids.has(id)) { detachPlayer(id); tile.remove(); tiles.delete(id); }
    }
    for (const v of wanted) {
      const status = v.status === "upcoming" ? "upcoming" : "live";
      const existing = tiles.get(v.id);
      if (!existing || existing.dataset.status !== status) {
        // New stream, or a scheduled one that has started: (re)load its player
        // in place so it plays.
        const tile = makeTile(v);
        tile.dataset.status = status;
        if (existing) {
          detachPlayer(v.id);
          existing.replaceWith(tile);
        } else {
          grid.appendChild(tile);
        }
        tiles.set(v.id, tile);
        attachPlayer(v.id, tile);
      }
    }
    emptyMsg.textContent = FILTER
      ? "No matching streams are live or scheduled for today."
      : "No streams are live or scheduled for today.";
    render();
  }

  async function poll() {
    try {
      const res = await fetch(BASE + "live.json?t=" + Date.now(), { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      update(Array.isArray(data.live) ? data.live : []);
    } catch (e) {
      if (!tiles.size) emptyMsg.textContent = "Couldn't load the live stream list. Retrying…";
    }
  }

  window.addEventListener("resize", render);
  poll();
  setInterval(poll, POLL_MS);
  setInterval(keepLive, CHECK_MS);
  // Also catch up whenever the tab becomes visible again, regardless of the timer.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) keepLive();
  });
})();
