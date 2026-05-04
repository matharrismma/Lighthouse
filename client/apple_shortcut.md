# Apple Shortcut — Share Sheet → seed

A two-action iOS Shortcut that turns the system Share Sheet into a
Concordance capture path. Highlight text in any app — Books, Mail,
a webpage, a PDF, a tweet, a sermon notes app — hit Share, pick
**Capture to Concordance**, and the highlight becomes a seed in
your journal tagged `source:apple_shortcut`.

Per the kingdom-economy substrate: works with the phone you
already own. No App Store gate, no payment processor in the path,
no proprietary client. Apple's Shortcuts app is built into iOS;
the Shortcut you build below uses only documented system actions.

## What the Shortcut does

1. **Receives** highlighted text from the Share Sheet (or from any
   app passing a string to the Shortcut).
2. **POSTs** it to your Concordance instance at `/capture` as JSON:

   ```json
   {
     "text": "<the shared text>",
     "source": "apple_shortcut",
     "source_meta": {
       "device": "iOS",
       "shortcut_version": "1"
     },
     "identity_acknowledged": true
   }
   ```

3. **Shows** the seed id returned by the engine, briefly, then
   disappears. No persistent UI; you stay in the app you were in.

## Build it (iOS 16+, ~90 seconds)

1. Open the **Shortcuts** app.
2. Tap **+** to create a new shortcut.
3. Tap the shortcut name (top of screen) → "Capture to Concordance".
4. Tap **Share Sheet** in the info panel → enable "Show in Share
   Sheet" → "Accepted Types" → set to **Text** only.
5. Add the following actions, in order:

   ### Action 1 — Get text from input

   - Search: **Get Text from Input**
   - Set "Get Text from Input" to **Shortcut Input**

   ### Action 2 — Get contents of URL (this is the POST)

   - Search: **Get Contents of URL**
   - URL: `https://narrowhighway.com/capture`
   - Tap **Show More**:
     - Method: **POST**
     - Headers: add one — `Content-Type` = `application/json`
     - Request Body: **JSON**
     - Add fields:
       - `text` — Type: Text — Value: tap the magic-variable picker, choose the **Text** from Action 1
       - `source` — Type: Text — Value: `apple_shortcut`
       - `identity_acknowledged` — Type: Boolean — Value: **true**

   ### Action 3 — Get dictionary value (extract seed id)

   - Search: **Get Dictionary Value**
   - Get: **Value**
   - Key: `entry.id` (Shortcuts supports dotted paths)
   - Dictionary: tap the magic-variable picker, pick **Contents of URL**

   ### Action 4 — Show notification (confirmation)

   - Search: **Show Notification**
   - Title: `Seed planted`
   - Body: tap the magic-variable picker, pick **Dictionary Value**
     from Action 3

6. Tap **Done**.

## Use it

- In **any app** with text: select text → **Share** → scroll to
  find **Capture to Concordance** (you may need to tap "Edit
  Actions" the first time to surface it).
- Or invoke directly from the Shortcuts widget on your home
  screen.
- Or via Siri: **"Hey Siri, capture to Concordance"** → speak the
  text.

## Self-hosted instance?

Replace `https://narrowhighway.com/capture` in Action 2 with your
own host. Same JSON shape, same response. The Shortcut works
identically against any Concordance deployment.

## Restricted-mode (per the deployment-modes doctrine)

When the engine is running in Restricted mode and requires a
physical alignment token, the Shortcut as described will receive
a 403 from `/capture` until the token is presented to the host.
This is by design — the wise-serpent posture means the same
client works in Open mode and falls back gracefully under
restriction.

## Notes on alignment

The `identity_acknowledged: true` field in Action 2 is the
plain-language doorway: by tapping the Shortcut, you're
acknowledging the canonical identity statement at
`https://narrowhighway.com/identity`. If you don't agree with it,
don't use the Shortcut. The engine doesn't validate this claim —
the four gates downstream check alignment by content, not by
the field — but the field is honest about what installation of
the Shortcut means.

## Versioning

The Shortcut format above is v1. Breaking changes will increment
the `shortcut_version` in `source_meta`. The `/capture` endpoint
is backward-compatible by design; old Shortcuts will continue to
work.
