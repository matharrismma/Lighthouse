"""One-time: post Hearth discussion threads for the 4 seeded radio
episodes (since they were produced before the cross-pollination was
wired in). Idempotent — re-running is safe.
"""
import json
import sys
sys.path.insert(0, '.')
from api import radio, hearth

EPS = [
    ("morning-devotion",    "2026-05-15"),
    ("the-walk",            "2026-05-11"),
    ("parable-hour",        "2026-05-12"),
    ("almanac-of-the-week", "2026-05-10"),
]

for slug, ep_date in EPS:
    show = radio.get_show(slug)
    json_path, mp3_path = radio._ep_paths(slug, ep_date)
    if not (mp3_path.exists() and json_path.exists()):
        print(f"{slug}/{ep_date}: no audio yet, skipping")
        continue
    rec = json.loads(json_path.read_text(encoding='utf-8'))
    room = radio.SHOW_HEARTH_ROOM.get(slug, 'front')
    marker = f"radio·{slug}·{ep_date}"
    existing = hearth.recent_messages(room, limit=200)
    if any(marker in (m.get('body') or '') for m in existing):
        print(f"{slug}/{ep_date}: already discussed in {room} (skipping)")
        continue
    body = radio._hearth_post_for_episode(show, rec, ep_date)
    posted = hearth.post_message(
        room=room,
        visitor_id=radio.RADIO_BOT_VISITOR_ID,
        handle=radio.RADIO_BOT_HANDLE,
        body=body,
    )
    print(f"{slug}/{ep_date}: posted to {room} as {posted['id']}")
