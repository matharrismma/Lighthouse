# QR codes — paper sneakernet

Print a sealed precedent as a QR; another instance scans → has it.
Survives every digital adversary. Books, sermon bulletins,
bulletin boards, printed devotionals can all carry QR pointers
that work offline forever.

Per the kingdom-economy substrate doctrine: when the network is
hostile or absent, paper still works. A QR carrying a URL is a
permanent, ungatekeepable distribution channel.

## What we don't do

We do not ship a QR generator. Phones already have QR rendering
software — any QR app on the App Store or F-Droid will turn a URL
into an image. Self-hosting our own encoder would add complexity
without giving you anything you don't already have. Wise as
serpents: use the tools that exist.

## URL forms that work as QRs

The engine has three URL surfaces designed to be QR-friendly:

### 1. Sealed precedents (online recipient)

```
https://<host>/ledger/<precedent_id>
```

The recipient scans → opens browser → sees the precedent on the
well. Works for anyone with internet. The precedent_id is a stable
permalink; QRs printed today still resolve in years.

This is the most-readable form. Encodes to a small QR (Version 3
or below for typical IDs).

### 2. Capture from share (any text)

```
https://<host>/share.html?text=<urlencoded text>
```

Already used by the Web Share Target on phones. Also works as a
QR: scanner opens the URL, share.html shows the text, user
confirms, it lands in their journal as `source:web_share`. Use
this for "here is a thought; if it speaks to you, plant it."

### 3. The well itself

```
https://<host>/
```

Lands on the journal page. The receiving device sees the live
engine; can browse the porch, search the well, etc. Useful as a
"come visit" QR rather than a "here's a specific record" QR.

## Generating a QR from a URL

Pick whichever you prefer:

| Tool | Where | Notes |
|---|---|---|
| **Phone QR app** | App Store / F-Droid | Most fully-featured QR apps include a generator. Type/paste URL, get image. |
| **`qrencode`** | Linux/macOS CLI (`apt install qrencode` / `brew install qrencode`) | `qrencode -o out.png 'https://...'` — sharp PNGs at any size. |
| **`segno`** | Python (`pip install segno`) | `segno.make('https://...').save('out.svg')` — SVG / PNG / EPS. |
| **`qrtool`** | Rust (`cargo install qrtool`) | Single-binary; useful inside scripts. |
| **A QR generator website** | Any | Quick one-offs. Watch the URL doesn't get logged. |

All of these are open-source and free at the substrate. None require
a payment processor or account.

## Generating a QR from the CLI (helper)

The engine ships a small `concordance qr` subcommand that emits the
appropriate URL given a precedent or seed id:

```
$ concordance qr <precedent_id>
https://narrowhighway.com/ledger/abc123def

$ concordance qr <precedent_id> --host https://my-host.example
https://my-host.example/ledger/abc123def

$ concordance qr --capture "Mt 5:37 — let your yes be yes."
https://narrowhighway.com/share.html?text=Mt%205%3A37%20...
```

Pipe that into your favorite QR generator:

```
$ concordance qr abc123def | xargs -I {} qrencode -o precedent.png '{}'
```

Or for a printable size:

```
$ concordance qr abc123def | xargs -I {} qrencode -o precedent.svg -t SVG -s 10 '{}'
```

## What to print

- **Sermon bulletins** — QR for the sealed precedent that captures
  the week's central decision or teaching anchor
- **Books and devotionals** — QR on the back cover pointing to the
  precedent that grounds the work
- **Bulletin boards and church kiosks** — sticker-sized QRs for
  recently-sealed community decisions
- **Business cards** — your engine's home page; let people find
  the well

## Restricted-mode considerations

When the network is hostile, the URL form (`/ledger/<id>`) requires
the receiving device to reach the host. Two options:

1. **Substitute Tor onion address.** If your engine runs as a Tor
   hidden service (see [`tor_onion.md`](tor_onion.md)), use the
   `xyz.onion` URL in your QRs. Recipients with Tor Browser scan
   and reach the engine through the onion.

2. **Embed full content (offline).** For totally air-gapped
   distribution, the QR can carry the full precedent record. This
   requires a larger QR (Version 20-40, ~3KB max) and is not yet
   wired into the engine's CLI. When this is built, it'll use the
   compact wire format already shipped for LoRa
   (`concordance_engine.wire`) plus a base64 wrapper. Track the
   roadmap.

## Connection to other channels

- **LoRa mesh** — QR + LoRa cover non-overlapping ranges. LoRa
  is electromagnetic; QR is paper. Both are kingdom-economy
  substrate.
- **Tor onion** — QRs encoding `.onion` URLs require Tor Browser
  but otherwise work identically. Substitution is one-line.
- **microSD sneakernet** — QRs are microSD's ancestor: paper
  passes the data without any networked infrastructure.

## Don't print private things

A QR is a public artifact. Don't QR-encode anything you wouldn't
post to the porch. Sealed precedents are appropriate (they survived
the four gates and are public by design). Personal journal entries
are not. Per the doctrine: the well is public; the journal is yours.
