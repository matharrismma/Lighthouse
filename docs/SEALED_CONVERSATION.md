# The Sealed Conversation

*One voice. One page that never restarts. The same conversation on every
device — and it cannot be turned into a way to watch you.*

This note ties the **Lighthouse Node hardware spec** (v3.1, §5.1 / §7.1 /
§11.2) to the **software shepherd** at narrowhighway.com. They are not two
products. They are one sealed conversation with two anchors: a hardware
secure element on the Node, a soft equivalent on phone and web.

---

## 0. The one mental model: two planes

Everything below rests on one separation. Get this right and the rest
follows; get it wrong and you build the thing you swore not to.

| | **Private plane** | **Public plane** |
|---|---|---|
| What lives here | your conversation, memory, household, money | seals people choose to publish, witnessed attestations, contributions |
| Who can read it | only you (and devices you enrolled) | anyone — it is meant to be seen |
| How it is stored | end-to-end encrypted; the server holds ciphertext it cannot read | signed, public records |
| Can it track you | **no — structurally impossible** | only what a person deliberately made public, under a name they chose |

**The conversation is private-plane. Community is public-plane.** They never
mix. This is what lets "one never-ending conversation across devices" and
"find the first people to build a community with" both be true without
contradiction — see §6.

---

## 1. Identity — a key you hold, not an account

The Node spec already states the principle (§5.1): the device keypair lives
in the soldered **ATECC608B** secure element; the private key *never leaves
it*. *"Possession is provably not authority."* A stolen recovery card is
"ciphertext plus signed artifacts it cannot re-sign."

The software shepherd mirrors this with a **soft Steward**: a keypair held in
the platform secure enclave / passkey (Face ID, Touch ID, Windows Hello
unlock it locally; the key never leaves the device). Phone and web each get
one.

The only "who" is a **public key**. No email, no phone, no name. The server —
and anyone who seizes it — learns *"key 7f3a returned,"* never *"Matt."*
Identity **authenticates without identifying**. The eye/voice you imagined is
the *local unlock* of this key, never a biometric sent anywhere.

We already own the software half: the engine's **Ed25519 identity**
(`identity_create` / `verify` / `fingerprint`) is exactly this key.

---

## 2. The conversation IS the sealed record chain

Read the Node's Trusted Record Path (§7.1) as a *conversation*, not a log.
Each turn is an append-only record with:

- payload + metadata,
- a **monotonic sequence number** (the Steward's own counter — the Main side
  cannot supply it),
- a **content digest**,
- a **countersignature** from the device key,
- **hash-linked** to the prior seal (each seal covers the previous seal's
  digest).

The spec's invariant: a malicious Main *"cannot manufacture sealed history,
reorder it, or delete it without detection."*

That is, precisely, **"one page that continues and never restarts,"** made
tamper-evident. The countersignature is the wax **seal** ("seal what holds")
— cryptographic, not decorative. Turn = sealed record; conversation = chain.

We own the software half here too: the engine's **hash-linked ledger** + the
`/seal` path are the soft form of §7.1. Unify them and the Node's record
chain and the shepherd's ledger are the *same* structure.

---

## 3. Cross-device — one conversation, many anchors

The ATECC608B is *per-device*. For a Node **and** a phone **and** this web
box to share **one** identity and **one** conversation, add a thin layer the
spec already seeds:

- **User cross-signing (enrollment).** A "person key" that each device's
  Steward (hardware SE or soft passkey) signs into. §5.1 already describes the
  ceremony for hardware replacement — *"export under user passphrase, import
  and re-anchor on the new SE."* Extend it from *replace a device* to *enroll
  an additional device*. No vendor, no account. This is how Signal/iMessage do
  multi-device: a self-signed device mesh under one user identity.

- **Encrypted sync (ECDH).** The ATECC608B (and every soft enclave) does
  P-256 ECDH. Derive a shared secret and **end-to-end encrypt the
  conversation blob**. Devices sync *through* the server; the server stores
  **ciphertext under your public key** and can never read it. Follow §7's own
  discipline: it deleted the "commit valve" as *"physically unimplementable"*
  and made trust **cryptographic** instead — do the same for sync. Don't
  promise a physical guarantee over a network; prove it with encryption +
  signatures.

**Fix to make first:** `/me/memory` today stores **plaintext** JSON keyed to
`X-Household-Id`. That single endpoint is where continuity would silently
become tracking. Encrypt client-side before it ever leaves the device; the
server keeps an opaque blob.

---

## 4. The anti-tracking guarantee (reactor, not bomb)

The Node spec already made this **canonical** — quote it back to yourself:

- §11.2, traceability: *"serial number, SE public key… recorded per unit;
  **no user data ever flows through this system.**"* Identity is separated
  from behavior at the factory.
- §11.2, anti-goal: *"provisioning must not create a vendor kill switch. The
  device certificate attests authenticity; its absence or revocation
  **degrades nothing locally. Canonical.**"*
- §7.2: *"no vendor server required to read exports."*

**The test that proves it.** *If someone seized the server tomorrow — bought
the company, served a warrant — what could they learn?* The only acceptable
answer: *"that some anonymous key synced encrypted bytes at unknown times."*
No content, no identity, no location, no timeline. If the answer includes any
of those, the design is wrong.

Concrete rules that keep it true:
- No per-identity access logs. No IP/geo/device retention on the private
  plane. Rate-limit by ephemeral token, not by identifying the person.
- No third party inside the private path. **This is why Cloudflare-as-proxy is
  a problem** — it terminates TLS and sees plaintext. Keep the private
  conversation/sync path terminating on your own hardware; reserve any CF
  proxy for the public marketing surface only.

---

## 5. One protocol, two anchors

Run the **soft Steward** on phone and web so a Node, a phone, and the book-box
all speak the **same sealed-record protocol** — hardware-anchored
(ATECC608B) or software-anchored (passkey/enclave). Same chain, same seals,
same identity model. The hardware spec and the software shepherd stop being
two documents.

---

## 6. Community forms on the public plane — never by watching

You want to find the first 2–3 people to build a community with. Do it
**without ever touching the private plane.**

The people who seed a community are not "the users we surveilled the most" —
they are **the people who raised their hand**: who **witnessed** a record by
name, **contributed** a precedent, **sealed** something publicly, or **joined
a group**. That is opt-in visibility, and it is the *only* honest measure of
"who is here." The engine already has this surface:

- `/community/contributors` (ranked) — who has publicly contributed.
- witness attestations (Ed25519, signed **by name** — Deut 19:15's "two or
  three") — who vouched for whom.
- `/community/activity`, `/community/badges`, `trust_index` — public standing.
- groups (`group_create` / `join`) — who chose to gather.

A **"First Fruits" founders view** built on *only* these — public, chosen,
named — surfaces your first 2–3 without a single line of behavioral tracking.
Aggregate "is anyone out there?" counts on the public site are fine; covert
per-person usage on the private conversation is exactly the bomb we refused.

**Rule:** the community leaderboard reads from the public plane only. If a
metric requires reading the private conversation, it does not get built.

---

## 7. What to build, in order

1. **Encrypt `/me/memory`** — client-side, key from the soft Steward. Closes
   the one place continuity leaks into tracking. *(smallest, highest value)*
2. **Sealed-record contract** — a `resume` + `append_turn` pair over the
   hash-linked ledger, so the conversation is one chain across sessions.
3. **User cross-signing / enrollment** — the device-mesh layer so phone +
   web + Node share one identity (extends §5.1's ceremony).
4. **ECDH encrypted sync** — server stores ciphertext; devices exchange
   encrypted deltas.
5. **First Fruits founders view** — public-plane only, per §6.

Items 1, 2, and 5 are buildable today on the existing engine (Ed25519
identity, ledger, seals, `/community/*`). Items 3–4 are the new crypto layer
the Node spec anchors.
