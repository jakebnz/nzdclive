#!/usr/bin/env python3
"""Write the channel's currently live streams to a JSON file.

Reads the public "Live" tab of the channel page (no API key needed) and keeps
only items that YouTube marks with a LIVE badge. Standard library only.

Usage: fetch_live.py OUTPUT_PATH
"""
import json
import re
import sys
import urllib.request

CHANNEL_ID = "UCuKowzPg2-A0FcmyPa3yWug"
URL = f"https://www.youtube.com/channel/{CHANNEL_ID}/streams"
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
LIVE_MARKERS = (
    '"THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE"',  # current lockupViewModel layout
    '"BADGE_STYLE_TYPE_LIVE_NOW"',  # older videoRenderer layout
)


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en",
            # Skip the EU cookie consent interstitial.
            "Cookie": "SOCS=CAI",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def initial_data(html):
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        raise SystemExit("ytInitialData not found; page layout may have changed")
    return json.loads(m.group(1))


def items(node):
    if isinstance(node, dict):
        for key in ("lockupViewModel", "videoRenderer"):
            if key in node:
                yield node[key]
        for value in node.values():
            yield from items(value)
    elif isinstance(node, list):
        for value in node:
            yield from items(value)


def title_of(item):
    try:
        return item["metadata"]["lockupMetadataViewModel"]["title"]["content"]
    except (KeyError, TypeError):
        pass
    try:
        return "".join(r["text"] for r in item["title"]["runs"])
    except (KeyError, TypeError):
        return ""


def is_live(item):
    blob = json.dumps(item)
    if any(marker in blob for marker in LIVE_MARKERS):
        return True
    overlays = item.get("thumbnailOverlays") or []
    return any(
        (o.get("thumbnailOverlayTimeStatusRenderer") or {}).get("style") == "LIVE"
        for o in overlays
    )


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    found = list(items(initial_data(fetch(URL))))
    if not found:
        raise SystemExit("no videos parsed; page layout may have changed")

    live, seen = [], set()
    for item in found:
        vid = item.get("contentId") or item.get("videoId") or ""
        if VIDEO_ID.match(vid) and vid not in seen and is_live(item):
            seen.add(vid)
            live.append({"id": vid, "title": title_of(item)[:200]})

    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        json.dump({"live": live}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"{len(live)} live of {len(found)} parsed: {[v['id'] for v in live]}")


if __name__ == "__main__":
    main()
