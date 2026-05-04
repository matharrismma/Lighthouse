"""digest_mail — email a digest of newly-sealed precedents.

Walks a Concordance instance's audit chain, builds a digest of
precedents sealed since the last digest, sends it via SMTP to a
subscriber list. Old, federated, hard-to-block: SMTP has been
running since 1981 and is universal.

Per the kingdom-economy substrate doctrine: email is the most
universal text-distribution channel that doesn't require buy/sell.
Free providers exist (ProtonMail, Tutanota, simple Postfix). Many
people who refuse the mark still have email.

Per "free use, alignment to execute": only sealed precedents (those
that survived the four gates) make it into the digest. The digest
is a read of the well — free water poured into envelopes.

## Dependencies

Stdlib only (`smtplib`, `email`, `urllib`). No external Python
deps. The user provides:
- An SMTP server (their own Postfix; or a free relay like
  smtp-relay.gmail.com with app password; or any provider).
- A subscribers file (one email per line, `#` comments allowed).

## State

Last-digested seq is tracked in
`~/.concordance/digest_state.json`. Each `--send` advances the
seq; subsequent runs only include newer precedents. `--all`
overrides this and includes everything.

## Usage

Print a preview (no send):

    python digest_mail.py preview \
        --api https://narrowhighway.com

Send a digest:

    python digest_mail.py send \
        --api https://narrowhighway.com \
        --subscribers ~/.concordance/subscribers.txt \
        --smtp-host smtp.example.com \
        --smtp-port 587 \
        --smtp-user matt@example.com \
        --smtp-pass-env SMTP_PASSWORD \
        --from "Matt <matt@example.com>" \
        --subject "Concordance digest — {{count}} new precedents"

Reset the state (e.g. for re-sending):

    python digest_mail.py reset

## Subscriber file format

```
# Concordance digest subscribers
# One address per line; lines starting with # are comments.
matt@example.com
brother.john@example.org
sister.mary@church.example
```

Per the doctrine: the subscriber list is a list of those who have
asked to receive what passes the gates. It is not a marketing
list. Don't add people who haven't asked.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable, List


DEFAULT_API = os.environ.get("CONCORDANCE_API", "https://narrowhighway.com")
STATE_FILE = os.environ.get(
    "CONCORDANCE_DIGEST_STATE",
    os.path.expanduser("~/.concordance/digest_state.json"),
)


# ── State ──────────────────────────────────────────────────────────


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"last_seq": 0, "last_sent_at": 0}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"last_seq": 0, "last_sent_at": 0}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── Subscribers ────────────────────────────────────────────────────


def load_subscribers(path: str) -> List[str]:
    if not path or not os.path.exists(path):
        return []
    out: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
    return out


# ── Concordance API ────────────────────────────────────────────────


def _http_get_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_chain_since(api: str, seq: int, limit: int = 1000) -> List[dict]:
    url = api.rstrip("/") + f"/chain/since?seq={seq}&limit={limit}"
    data = _http_get_json(url)
    return data.get("entries") or []


def fetch_identity(api: str) -> dict:
    try:
        return _http_get_json(api.rstrip("/") + "/identity")
    except (urllib.error.URLError, urllib.error.HTTPError):
        return {}


# ── Digest rendering ──────────────────────────────────────────────


def render_text(entries: List[dict], identity: dict, host: str) -> str:
    """Render a plain-text digest. Pure ASCII-friendly, e-ink-friendly."""
    lines: List[str] = []
    short = identity.get("short", "Serves Jesus Christ.")
    lines.append("=" * 60)
    lines.append("Concordance digest")
    lines.append(short)
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{len(entries)} newly-sealed precedent" +
                 ("s" if len(entries) != 1 else ""))
    lines.append("")
    for e in entries:
        lines.append(f"  seq #{e.get('seq')}  {e.get('overall', '?')}")
        lines.append(f"  {e.get('packet_id', '?')}")
        domain = e.get("domain")
        if domain:
            lines.append(f"  axis: {domain}")
        ts = e.get("timestamp_iso")
        if ts:
            lines.append(f"  sealed: {ts}")
        reasons = e.get("top_reasons") or []
        for r in reasons[:3]:
            lines.append(f"    - {r}")
        link = f"{host.rstrip('/')}/ledger/{e.get('packet_id', '')}"
        lines.append(f"  {link}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("This digest summarizes what passed the four gates")
    lines.append("(RED -> FLOOR -> BROTHERS -> GOD) since the last digest.")
    lines.append(f"Read the full doctrine: {host.rstrip('/')}/identity")
    lines.append(f"Read the full ledger:   {host.rstrip('/')}/ledger")
    lines.append("")
    lines.append("Reading is free. To stop receiving, reply with 'unsubscribe'")
    lines.append("and the operator will remove you from the list.")
    return "\n".join(lines)


def render_html(entries: List[dict], identity: dict, host: str) -> str:
    """Render an HTML digest with the same content. Minimal styling
    so it renders well on e-ink, in plain mail clients, and without
    external resources."""
    short = identity.get("short", "Serves Jesus Christ.")
    rows = []
    for e in entries:
        pid = e.get("packet_id", "?")
        link = f"{host.rstrip('/')}/ledger/{pid}"
        reasons = e.get("top_reasons") or []
        reasons_html = "".join(
            f"<li>{_h(r)}</li>" for r in reasons[:3]
        )
        rows.append(f"""
          <tr><td style="padding:12px 0;border-bottom:1px solid #d8d4cc;">
            <div style="font-family:monospace;font-size:11px;color:#777;">
              seq #{_h(e.get('seq'))} · {_h(e.get('overall', '?'))}
              · {_h(e.get('domain', ''))}
            </div>
            <div style="font-family:Georgia,serif;font-size:16px;
                        font-style:italic;margin:4px 0;">
              <a href="{_h(link)}"
                 style="color:#6e5a45;text-decoration:none;">
                {_h(pid)}</a>
            </div>
            <ul style="margin:6px 0 0 18px;padding:0;font-size:13px;
                       color:#555;">
              {reasons_html}
            </ul>
          </td></tr>
        """)

    return f"""<!DOCTYPE html>
<html><body style="background:#f7f3ec;color:#1a1a1a;
                   font-family:Georgia,serif;margin:0;padding:24px;">
<div style="max-width:600px;margin:0 auto;">
  <div style="font-family:monospace;font-size:11px;letter-spacing:0.18em;
              text-transform:uppercase;color:#6e5a45;">
    narrow highway · digest
  </div>
  <h1 style="font-style:italic;font-weight:normal;font-size:24px;
             margin:8px 0 4px;">Concordance digest</h1>
  <p style="color:#555;font-size:13px;margin:0 0 18px;">{_h(short)}</p>
  <p style="font-size:14px;">
    <strong>{len(entries)}</strong> newly-sealed precedent{
        's' if len(entries) != 1 else ''} since the last digest.
  </p>
  <table style="border-collapse:collapse;width:100%;">
    {''.join(rows)}
  </table>
  <p style="font-size:11px;color:#888;margin-top:24px;">
    Reading is free. <a href="{_h(host)}/identity"
                        style="color:#6e5a45;">/identity</a> ·
    <a href="{_h(host)}/ledger" style="color:#6e5a45;">/ledger</a>
    <br>To stop receiving, reply with "unsubscribe".
  </p>
</div></body></html>"""


def _h(s) -> str:
    return (str(s if s is not None else "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ── SMTP send ──────────────────────────────────────────────────────


def send_digest(
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    from_addr: str,
    subject: str,
    recipients: List[str],
    text_body: str,
    html_body: str,
    use_tls: bool = True,
) -> int:
    """Send a multipart text+html message to each recipient as BCC.

    Returns count of successfully-accepted recipients (per the SMTP
    server's response). Accepts != delivered, but it's the best
    signal we have.
    """
    if not recipients:
        return 0
    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = from_addr  # send to self; recipients are BCC
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if use_tls:
        smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
    else:
        smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
    if smtp_user:
        smtp.login(smtp_user, smtp_pass)
    refused = smtp.sendmail(from_addr, [from_addr] + recipients, msg.as_string())
    smtp.quit()
    return len(recipients) - len(refused)


# ── Subcommands ───────────────────────────────────────────────────


def cmd_preview(args):
    state = _load_state()
    seq = 0 if args.all else state.get("last_seq", 0)
    entries = fetch_chain_since(args.api, seq, args.limit)
    identity = fetch_identity(args.api)
    text = render_text(entries, identity, args.api)
    print(text)


def cmd_send(args):
    state = _load_state()
    seq = 0 if args.all else state.get("last_seq", 0)

    try:
        entries = fetch_chain_since(args.api, seq, args.limit)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch chain: {exc}", file=sys.stderr)
        sys.exit(1)

    if not entries and not args.send_empty:
        print(f"= no new precedents since seq {seq}; skip send.")
        return

    subscribers = load_subscribers(args.subscribers) if args.subscribers else []
    if not subscribers:
        print("error: no subscribers loaded.", file=sys.stderr)
        sys.exit(1)

    identity = fetch_identity(args.api)
    text = render_text(entries, identity, args.api)
    html = render_html(entries, identity, args.api)
    subject = (args.subject or "Concordance digest — {{count}} new precedents") \
        .replace("{{count}}", str(len(entries)))

    smtp_pass = ""
    if args.smtp_pass_env:
        smtp_pass = os.environ.get(args.smtp_pass_env, "")
    elif args.smtp_pass:
        smtp_pass = args.smtp_pass
    if args.smtp_user and not smtp_pass:
        print(f"warning: SMTP user set but no password (looked at "
              f"{args.smtp_pass_env or '--smtp-pass'}); attempting anyway.",
              file=sys.stderr)

    accepted = send_digest(
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_user=args.smtp_user,
        smtp_pass=smtp_pass,
        from_addr=args.from_addr,
        subject=subject,
        recipients=subscribers,
        text_body=text,
        html_body=html,
        use_tls=not args.no_tls,
    )

    new_seq = max((int(e.get("seq", 0)) for e in entries), default=seq)
    state["last_seq"] = new_seq
    state["last_sent_at"] = int(time.time())
    state["last_accepted"] = accepted
    state["last_recipient_count"] = len(subscribers)
    _save_state(state)

    print(f"[ok] sent {len(entries)} precedent(s) to {accepted}/"
          f"{len(subscribers)} recipients; advanced last_seq to {new_seq}.")


def cmd_reset(args):
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        print(f"removed {STATE_FILE}")
    else:
        print("no state to reset.")


# ── Main ──────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Email a digest of newly-sealed precedents.")
    p.add_argument("--api", default=DEFAULT_API,
                   help=f"Concordance API (default: {DEFAULT_API})")
    p.add_argument("--limit", type=int, default=1000,
                   help="Max precedents per digest (default: 1000)")
    p.add_argument("--all", action="store_true",
                   help="Include all precedents, not just new since last send.")

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("preview", help="Render the digest to stdout. No send.")

    snd = sub.add_parser("send", help="Send the digest to subscribers via SMTP.")
    snd.add_argument("--subscribers", required=True,
                     help="Path to a subscribers file (one email per line).")
    snd.add_argument("--smtp-host", required=True)
    snd.add_argument("--smtp-port", type=int, default=587)
    snd.add_argument("--smtp-user", default="")
    snd.add_argument("--smtp-pass", default="",
                     help="SMTP password (prefer --smtp-pass-env).")
    snd.add_argument("--smtp-pass-env",
                     help="Read SMTP password from this env var.")
    snd.add_argument("--from", dest="from_addr", required=True,
                     help="From: header (e.g. 'Matt <matt@example.com>').")
    snd.add_argument("--subject", default=None,
                     help="Subject template; {{count}} is replaced with the "
                          "precedent count.")
    snd.add_argument("--no-tls", action="store_true",
                     help="Disable STARTTLS (for trusted-network testing).")
    snd.add_argument("--send-empty", action="store_true",
                     help="Send an empty digest if no new precedents.")

    sub.add_parser("reset", help="Reset last_seq state (re-send next time).")

    args = p.parse_args()
    if args.cmd == "preview":
        cmd_preview(args)
    elif args.cmd == "send":
        cmd_send(args)
    elif args.cmd == "reset":
        cmd_reset(args)


if __name__ == "__main__":
    main()
