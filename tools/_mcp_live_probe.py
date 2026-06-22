"""Live probe: confirm the agent-facing MCP tools reach the whole ~11k-card
keeping. Run on the droplet with the venv python against the running /mcp:

    /home/nh/Lighthouse/.venv/bin/python /tmp/_mcp_live_probe.py
"""
import httpx, json

BASE = "http://127.0.0.1:8000/mcp/"
H = {"Content-Type": "application/json",
     "Accept": "application/json, text/event-stream"}
CORPUS_PREFIXES = ("card_", "dictionary_", "classics_", "patristics_")


def parse(r):
    if "text/event-stream" in r.headers.get("content-type", ""):
        for line in r.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    try:
        return r.json()
    except Exception:
        return {"_raw": r.text[:300]}


def tool_call(c, headers, name, args):
    r = c.post(BASE, headers=headers, json={
        "jsonrpc": "2.0", "id": 99, "method": "tools/call",
        "params": {"name": name, "arguments": args}})
    obj = parse(r)
    res = (obj or {}).get("result", {})
    content = res.get("content") if isinstance(res, dict) else None
    if content:
        return json.loads(content[0].get("text", "{}"))
    return {"_obj": obj}


def is_corpus(i):
    return bool(i) and i.startswith(CORPUS_PREFIXES)


with httpx.Client(timeout=60, follow_redirects=True) as c:
    r = c.post(BASE, headers=H, json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "probe", "version": "1"}}})
    sid = r.headers.get("mcp-session-id")
    H2 = dict(H)
    if sid:
        H2["mcp-session-id"] = sid
    c.post(BASE, headers=H2, json={"jsonrpc": "2.0",
                                   "method": "notifications/initialized"})

    passes = []

    # (3) search interleaves almanac + corpus
    data = tool_call(c, H2, "search", {"query": "Augustine grace",
                                       "max_results": 8})
    ids = [x.get("id") for x in data.get("results", [])]
    corpus_ids = [i for i in ids if is_corpus(i)]
    print("search corpus hits:", corpus_ids)
    passes.append(("search reaches corpus", bool(corpus_ids)))

    # (3) fetch resolves a corpus card id
    if corpus_ids:
        f = tool_call(c, H2, "fetch", {"id": corpus_ids[0]})
        meta = f.get("metadata", {}) if isinstance(f, dict) else {}
        ok = meta.get("found") and meta.get("via") == "corpus"
        print("fetch", corpus_ids[0], "-> found:", meta.get("found"),
              "via:", meta.get("via"), "len:", len(f.get("text", "")))
        passes.append(("fetch resolves corpus id", bool(ok)))

    # (4) topical tools additively surface 'also_in_the_keeping'
    def also_ok(label, data):
        sec = data.get("also_in_the_keeping") if isinstance(data, dict) else None
        n = (sec or {}).get("count", 0)
        cards = (sec or {}).get("cards", [])
        print(f"{label}: also_in_the_keeping count={n} "
              f"sample={[x.get('id') for x in cards[:2]]}")
        passes.append((f"{label} de-siloed", n > 0))

    also_ok("apothecary_compound",
            tool_call(c, H2, "apothecary_compound", {"condition": "anxiety"}))
    also_ok("almanac(query)",
            tool_call(c, H2, "almanac", {"query": "grace", "limit": 4}))
    also_ok("packets_search",
            tool_call(c, H2, "packets_search", {"query": "forgiveness",
                                                "limit": 6}))

    print("\n--- VERDICT ---")
    for name, ok in passes:
        print(("PASS " if ok else "FAIL ") + name)
    print("ALL PASS" if all(p for _, p in passes) else "SOME FAILED")
