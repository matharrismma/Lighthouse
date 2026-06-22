"""Throwaway probe: call the LIVE /mcp endpoint and report whether search()
and fetch() now reach the corpus. Run on the droplet with the venv python."""
import httpx, json, sys

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

    # --- search ---
    data = tool_call(c, H2, "search", {"query": "Augustine grace",
                                       "max_results": 8})
    ids = [x.get("id") for x in data.get("results", [])]
    corpus_ids = [i for i in ids if i and i.startswith(CORPUS_PREFIXES)]
    print("search ids        :", ids)
    print("search corpus hits:", corpus_ids)

    # --- fetch a corpus card id, if we got one ---
    if corpus_ids:
        f = tool_call(c, H2, "fetch", {"id": corpus_ids[0]})
        meta = f.get("metadata", {}) if isinstance(f, dict) else {}
        print("fetch", corpus_ids[0], "->", f.get("title"),
              "| found:", meta.get("found"), "| via:", meta.get("via"),
              "| text_len:", len(f.get("text", "")))
    else:
        print("fetch: SKIPPED (no corpus id surfaced by search)")

    print("VERDICT:", "PASS — agent search reaches the corpus"
          if corpus_ids else "FAIL — still siloed to the almanac")
