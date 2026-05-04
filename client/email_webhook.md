# Email-in — forward an email, plant a seed

The most decentralized capture path. SMTP is the oldest open
standard on the internet. Every email provider works. No app
store, no payment processor, no platform that can deplatform.

## How it works

1. A user forwards (or sends directly to) an inbound address —
   `seed@yourdomain.com`, `inbox@yourdomain.com`, anything you
   designate.
2. An inbound-email service (Postmark, SendGrid Inbound Parse,
   Mailgun Routes, Cloudflare Email Routing → Worker, or self-
   hosted) receives it.
3. The service POSTs a JSON payload to the engine's `/capture`
   endpoint with the email's text body.
4. The engine plants the seed, tagged `source:email`, with the
   sender / subject / message-id preserved in `source_meta`.

The engine never speaks SMTP itself. We always sit *behind* an
inbound-email service, because (a) SMTP servers are a
maintenance-heavy attack surface and (b) every reputable inbound
service offers a free tier sufficient for kingdom-economy use.

## Choosing a service

Per the wise-serpent / innocent-dove posture, prefer providers
whose free tier is documented and whose terms don't conflict with
the engine's purpose. As of late 2025, options worth knowing:

| Service | Free tier | Mark-economy alignment | Notes |
|---|---|---|---|
| **Cloudflare Email Routing → Worker** | Generous; no credit card | High | Routes emails to a Worker; Worker POSTs to `/capture`. Most decentralized of the lot. |
| **Postmark** | Free for testing; paid for production | Medium | Clean Inbound Parse format; reliable. Requires payment for prod volume. |
| **SendGrid Inbound Parse** | Limited free | Medium | Twilio-owned; phone-number signup. Less aligned. |
| **Mailgun Routes** | Limited free | Medium | Reliable; multipart/form-encoded payload. |
| **Self-hosted (Postfix → script)** | Free forever | Highest | Full control; runs on any VPS. Requires SMTP ops knowledge. |

The Cloudflare path is the recommended default — free, well
documented, and the Worker code that bridges to `/capture` is
~30 lines.

## Adapter format expected by `/capture`

Whatever service you use, the final POST to the engine should look
like this:

```json
POST /capture
Content-Type: application/json

{
  "text": "<the email body, plain-text preferred over HTML>",
  "source": "email",
  "source_meta": {
    "from": "matt@example.com",
    "to": "seed@yourdomain.com",
    "subject": "Quick thought on Mt 5:37",
    "message_id": "<...@mail.example.com>",
    "received_at_epoch": 1730000000
  },
  "identity_acknowledged": true
}
```

`text` is required; everything else is optional but useful. The
`source_meta.from` lets you later filter "all seeds I forwarded
from my own email" vs "everything anyone sent in." The
`message_id` lets you de-duplicate if the same email arrives
twice.

## Cloudflare Email Routing → Worker (recommended path)

1. **Add a domain to Cloudflare.** Free.
2. **Enable Email Routing** for that domain. Free.
3. **Create a Worker** with the code below. Free tier is 100k
   requests/day — vastly more than personal capture.
4. **Add an Email Worker route**: anything sent to
   `seed@yourdomain.com` is delivered to the Worker.
5. The Worker reads the email, extracts the text body, POSTs to
   `/capture`.

### Minimal Worker (JavaScript)

```js
// concordance-email-worker.js
//
// Cloudflare Email Worker that forwards inbound mail to a
// Concordance instance's /capture endpoint.
//
// Configure CONCORDANCE_API as an environment variable (defaults
// to https://narrowhighway.com).

import PostalMime from 'postal-mime';

export default {
  async email(message, env, ctx) {
    const api = (env.CONCORDANCE_API || 'https://narrowhighway.com').replace(/\/$/, '');

    // Parse the raw RFC822 email.
    const parser = new PostalMime();
    const raw = await new Response(message.raw).arrayBuffer();
    const parsed = await parser.parse(raw);

    const text = (parsed.text || parsed.html || '').trim();
    if (!text) {
      // Nothing to plant. Don't throw — accept the message silently.
      return;
    }

    const body = {
      text,
      source: 'email',
      source_meta: {
        from:        parsed.from?.address || message.from,
        to:          message.to,
        subject:     parsed.subject || '(no subject)',
        message_id:  parsed.messageId || null,
        received_at_epoch: Math.floor(Date.now() / 1000)
      },
      identity_acknowledged: true
    };

    const r = await fetch(api + '/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    if (!r.ok) {
      // Reject the email so the sender's MTA may retry.
      message.setReject('Concordance capture failed: ' + r.status);
    }
  }
};
```

### Self-hosted alternative (Postfix → Python script)

If you'd rather not depend on Cloudflare, run your own MTA. Add
this to `/etc/aliases` (or your equivalent):

```
seed: |/usr/local/bin/concordance-email-deliver
```

And put this script at `/usr/local/bin/concordance-email-deliver`:

```python
#!/usr/bin/env python3
"""Deliver an email piped on stdin to /capture."""
import email, json, os, sys, time, urllib.request

API = os.environ.get('CONCORDANCE_API', 'https://narrowhighway.com').rstrip('/')
msg = email.message_from_file(sys.stdin)

def get_body(m):
    if m.is_multipart():
        for part in m.walk():
            if part.get_content_type() == 'text/plain':
                return part.get_payload(decode=True).decode('utf-8', errors='replace')
        for part in m.walk():
            if part.get_content_type() == 'text/html':
                return part.get_payload(decode=True).decode('utf-8', errors='replace')
        return ''
    return m.get_payload(decode=True).decode('utf-8', errors='replace')

text = get_body(msg).strip()
if not text:
    sys.exit(0)

body = json.dumps({
    'text': text,
    'source': 'email',
    'source_meta': {
        'from':       msg.get('From'),
        'to':         msg.get('To'),
        'subject':    msg.get('Subject'),
        'message_id': msg.get('Message-ID'),
        'received_at_epoch': int(time.time())
    },
    'identity_acknowledged': True
}).encode('utf-8')

req = urllib.request.Request(
    API + '/capture',
    data=body,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
urllib.request.urlopen(req, timeout=30)
```

`chmod +x` the script. Now any email to `seed@yourdomain.com`
becomes a journal seed.

## Restricted-mode considerations

Under the deployment-modes doctrine, when the engine is running
in Restricted mode the `/capture` endpoint may require a physical
alignment token. The email path will fail closed in that case —
inbound services receive 403 and (depending on configuration)
either bounce the email or accept it silently. The substrate
remains intact; the entrypoint is just paused until the operator
presents the token.

## Privacy notes

- Email subject and from-address are recorded in `source_meta`.
  If this matters for your community, strip them in the Worker
  before forwarding.
- The engine does not read inbound email; it receives whatever
  the Worker chooses to forward. The Worker code is the trust
  boundary.
- Don't forward anything you wouldn't write into your own
  journal. Email-in is a pipe, not a filter.
