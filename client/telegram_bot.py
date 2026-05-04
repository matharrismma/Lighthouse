"""telegram_bot — Telegram messages become journal seeds.

A standalone Python script. Runs anywhere Python runs. Polls
Telegram's Bot API (no webhook required, no public IP needed),
forwards each incoming message to a Concordance `/capture`
endpoint, replies with the seed id.

Per the wise-serpent / innocent-dove posture:
- Telegram is free, well-documented, and works without phone-
  number lookup of message senders. The bot's own account does
  need a phone number to register at @BotFather, but bot
  *users* are identified only by Telegram user IDs.
- The script never stores message content locally; it forwards
  and replies. No exfiltration of conversation history.
- We document exactly which user IDs are allowed to capture
  (the `--allow` flag) — innocence is enforced by config, not
  by trust of the network.

Per the deployment-modes doctrine, this is Open / Restricted
substrate; under Lockdown the script simply isn't running.

## One-time setup

1. Open Telegram. Talk to **@BotFather**: `/newbot`. Give it a
   name. BotFather replies with an HTTP API token like
   `1234567890:ABC...`.
2. Find your own Telegram user ID. Talk to **@userinfobot**;
   it replies with your numeric ID.
3. Run the script:

       python telegram_bot.py \
           --token 1234567890:ABC... \
           --allow 999999999 \
           --api https://narrowhighway.com

   (Or set environment variables `TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_ALLOW_USER_IDS`, and `CONCORDANCE_API`.)

4. Send your bot a message. It captures + replies with the seed
   id.

## Zero external dependencies

Stdlib only — `urllib.request`, `json`, `time`. Same posture as
`watch_folder.py`. Will run on a Raspberry Pi, a $5 VPS, your
laptop, or a microSD-bootable system.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable, Optional, Set


DEFAULT_API = "https://narrowhighway.com"
DEFAULT_POLL_TIMEOUT = 25  # long-poll seconds (Telegram caps at ~50)
TG_API = "https://api.telegram.org"


# ── Telegram API helpers ────────────────────────────────────────────

def tg(token: str, method: str, **params) -> dict:
    """Call the Telegram Bot API. Returns the parsed `result` field."""
    url = f"{TG_API}/bot{token}/{method}"
    if params:
        # Telegram accepts JSON bodies for everything; cleaner than
        # form-encoding because of nested objects in some methods.
        body = json.dumps(params).encode("utf-8")
        headers = {"Content-Type": "application/json"}
    else:
        body = None
        headers = {}
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=DEFAULT_POLL_TIMEOUT + 5) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("ok"):
        raise RuntimeError(f"telegram error: {data.get('description')!r}")
    return data.get("result")


def get_updates(token: str, offset: Optional[int]) -> list:
    """Long-poll for new updates. Returns a list (possibly empty)."""
    return tg(
        token, "getUpdates",
        offset=offset,
        timeout=DEFAULT_POLL_TIMEOUT,
        allowed_updates=["message"],
    )


def reply(token: str, chat_id: int, text: str, reply_to: Optional[int] = None) -> None:
    """Send a reply to a chat. Best-effort; failures are logged not raised."""
    try:
        params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_to:
            params["reply_to_message_id"] = reply_to
        tg(token, "sendMessage", **params)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
        print(f"[warn] reply failed: {exc}", file=sys.stderr)


# ── Concordance capture ─────────────────────────────────────────────

def post_capture(api: str, text: str, *, source_meta: dict) -> dict:
    """POST to /capture. Returns the parsed JSON response."""
    url = api.rstrip("/") + "/capture"
    body = json.dumps({
        "text": text,
        "source": "telegram",
        "source_meta": source_meta,
        "identity_acknowledged": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Main loop ───────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Telegram bot that captures messages as journal seeds."
    )
    p.add_argument("--token", default=os.environ.get("TELEGRAM_BOT_TOKEN"),
                   help="Telegram bot token from @BotFather "
                        "(or env TELEGRAM_BOT_TOKEN)")
    p.add_argument("--allow", action="append", default=None,
                   help="Telegram user ID allowed to capture. May be passed "
                        "multiple times. Defaults to env TELEGRAM_ALLOW_USER_IDS "
                        "(comma-separated). If empty, *no one* is allowed and "
                        "the bot logs every received message but captures none.")
    p.add_argument("--api", default=os.environ.get("CONCORDANCE_API", DEFAULT_API),
                   help=f"Concordance API base URL (default: {DEFAULT_API}; "
                        "or env CONCORDANCE_API)")
    args = p.parse_args()

    if not args.token:
        print("error: --token (or TELEGRAM_BOT_TOKEN) is required", file=sys.stderr)
        sys.exit(2)

    # Normalize allow-list. If the flag was used, args.allow is a list of
    # strings. Otherwise fall back to env var.
    if args.allow:
        allow_raw = args.allow
    else:
        env = os.environ.get("TELEGRAM_ALLOW_USER_IDS", "")
        allow_raw = [s.strip() for s in env.split(",") if s.strip()]
    allow: Set[int] = set()
    for s in allow_raw:
        try:
            allow.add(int(s))
        except ValueError:
            print(f"[warn] ignoring non-numeric allow entry: {s!r}",
                  file=sys.stderr)

    print(f"[bot] api:   {args.api}")
    if allow:
        print(f"[bot] allow: {sorted(allow)}")
    else:
        print("[bot] allow: <empty> — no user can capture; received messages are logged only")

    # Identify the bot itself, mostly to confirm the token works.
    try:
        me = tg(args.token, "getMe")
        print(f"[bot] running as @{me.get('username')} (id {me.get('id')})")
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
        print(f"error: getMe failed: {exc}", file=sys.stderr)
        sys.exit(1)

    offset: Optional[int] = None
    try:
        while True:
            try:
                updates = get_updates(args.token, offset)
            except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
                print(f"[warn] getUpdates failed: {exc}", file=sys.stderr)
                time.sleep(5)
                continue

            for upd in updates:
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue
                user = msg.get("from") or {}
                user_id = user.get("id")
                chat_id = (msg.get("chat") or {}).get("id")
                text = (msg.get("text") or "").strip()
                username = user.get("username") or user.get("first_name") or "?"

                if not text:
                    # Photos, stickers, voice notes, etc. — log only.
                    print(f"[skip] {username}: non-text message")
                    continue

                if user_id not in allow:
                    print(f"[deny] {username} ({user_id}): not in allow-list")
                    reply(args.token, chat_id,
                          "You're not in this bot's allow-list. Ask the operator "
                          "to add your user ID.",
                          reply_to=msg.get("message_id"))
                    continue

                try:
                    result = post_capture(
                        args.api,
                        text,
                        source_meta={
                            "telegram_user_id": user_id,
                            "telegram_username": user.get("username"),
                            "telegram_chat_id": chat_id,
                            "telegram_message_id": msg.get("message_id"),
                            "received_at_epoch": time.time(),
                        },
                    )
                except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                    print(f"[err ] capture failed for {username}: {exc}",
                          file=sys.stderr)
                    reply(args.token, chat_id,
                          f"Capture failed: {exc}",
                          reply_to=msg.get("message_id"))
                    continue
                except Exception as exc:  # noqa: BLE001
                    print(f"[err ] unexpected: {exc}", file=sys.stderr)
                    reply(args.token, chat_id,
                          f"Unexpected error: {exc}",
                          reply_to=msg.get("message_id"))
                    continue

                seed_id = (result.get("entry") or {}).get("id", "?")
                print(f"[ok  ] {username} -> {seed_id}")
                reply(args.token, chat_id,
                      f"Seed planted: <code>{seed_id}</code>",
                      reply_to=msg.get("message_id"))
    except KeyboardInterrupt:
        print("\n[bot] stopped", file=sys.stderr)


if __name__ == "__main__":
    main()
