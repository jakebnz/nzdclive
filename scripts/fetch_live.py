#!/usr/bin/env python3
"""Write the channel's live streams, and public streams scheduled for today,
to a JSON file.

Reads the public "Live" tab of the channel page (no API key needed). Items
with a LIVE badge are live now; items with an "Upcoming" badge are scheduled.
The listing only shows a scheduled stream's start time as display text, so the
exact start time is looked up per video, and only streams starting on today's
date in New Zealand time are kept. Standard library only.

Usage: fetch_live.py OUTPUT_PATH
"""
import datetime
import json
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

CHANNEL_ID = "UCuKowzPg2-A0FcmyPa3yWug"
URL = f"https://www.youtube.com/channel/{CHANNEL_ID}/streams"
SEARCH_URL = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
FALLBACK_CLIENT_VERSION = "2.20261119.07.00"
TZ = ZoneInfo("Pacific/Auckland")
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
LIVE_MARKERS = (
    '"THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE"',  # current lockupViewModel layout
    '"BADGE_STYLE_TYPE_LIVE_NOW"',  # older videoRenderer layout
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en",
    # Skip the EU cookie consent interstitial.
    "Cookie": "SOCS=CAI",
}


def request(url, body=None):
    headers = dict(HEADERS)
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
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


def video_id(item):
    vid = item.get("contentId") or item.get("videoId") or ""
    return vid if VIDEO_ID.match(vid) else ""


def title_of(item):
    try:
        return item["metadata"]["lockupMetadataViewModel"]["title"]["content"]
    except (KeyError, TypeError):
        pass
    try:
        return "".join(r["text"] for r in item["title"]["runs"])
    except (KeyError, TypeError):
        return ""


def overlay_styles(item):
    return {
        (o.get("thumbnailOverlayTimeStatusRenderer") or {}).get("style")
        for o in item.get("thumbnailOverlays") or []
    }


def is_live(item):
    blob = json.dumps(item)
    return any(m in blob for m in LIVE_MARKERS) or "LIVE" in overlay_styles(item)


def is_upcoming(item):
    if "upcomingEventData" in item or "UPCOMING" in overlay_styles(item):
        return True
    blob = json.dumps(item)
    return '"text": "Upcoming"' in blob or '"content": "Scheduled for ' in blob


def start_time(vid, client_version):
    """Exact scheduled start (Unix seconds) of an upcoming video, or None."""
    body = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": client_version,
                "hl": "en",
                "gl": "NZ",
            }
        },
        "query": f'"{vid}"',
    }
    try:
        data = json.loads(request(SEARCH_URL, body))
    except Exception as exc:  # network or JSON problem: skip this video
        print(f"warning: start time lookup failed for {vid}: {exc}")
        return None
    for item in items(data):
        if item.get("videoId") == vid:
            start = str((item.get("upcomingEventData") or {}).get("startTime", ""))
            if start.isdigit():
                return int(start)
    print(f"warning: no start time found for {vid}")
    return None


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    html = request(URL)
    m = re.search(r'"INNERTUBE_CLIENT_VERSION":"([0-9.]+)"', html)
    client_version = m.group(1) if m else FALLBACK_CLIENT_VERSION

    found = list(items(initial_data(html)))
    if not found:
        raise SystemExit("no videos parsed; page layout may have changed")

    today = datetime.datetime.now(TZ).date()
    live, upcoming, seen = [], [], set()
    for item in found:
        vid = video_id(item)
        if not vid or vid in seen:
            continue
        seen.add(vid)
        title = title_of(item)[:200]
        if is_live(item):
            live.append({"id": vid, "title": title, "status": "live"})
        elif is_upcoming(item):
            start = start_time(vid, client_version)
            if start is None:
                continue
            day = datetime.datetime.fromtimestamp(start, TZ).date()
            if day == today:
                upcoming.append(
                    {"id": vid, "title": title, "status": "upcoming", "start": start}
                )

    upcoming.sort(key=lambda v: v["start"])
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        json.dump({"live": live + upcoming}, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(
        f"{len(live)} live, {len(upcoming)} scheduled today ({today}), "
        f"{len(found)} parsed: {[v['id'] for v in live + upcoming]}"
    )


if __name__ == "__main__":
    main()
