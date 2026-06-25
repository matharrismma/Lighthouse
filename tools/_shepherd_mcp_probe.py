"""Confirm the MCP `shepherd_answer` tool is live via a FRESH /mcp session."""
import httpx, json
BASE = "http://127.0.0.1:8000/mcp/"
H = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def parse(r):
    if "text/event-stream" in r.headers.get("content-type", ""):
        for line in r.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return r.json()


with httpx.Client(timeout=60, follow_redirects=True) as c:
    r = c.post(BASE, headers=H, json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "probe", "version": "1"}}})
    sid = r.headers.get("mcp-session-id")
    H2 = dict(H)
    if sid:
        H2["mcp-session-id"] = sid
    c.post(BASE, headers=H2, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    r = c.post(BASE, headers=H2, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "shepherd_answer", "arguments": {"q": "what does the bible say about anxiety"}}})
    obj = parse(r)
    d = json.loads(obj["result"]["content"][0]["text"])
    print("mode:", d.get("mode"))
    print("answer:", (d.get("answer") or "")[:160])
    print("cards:", [c.get("title", "")[:40] for c in d.get("grounded_cards", [])][:3])
    print("MCP shepherd_answer:", "PASS" if d.get("mode") == "answer" and d.get("grounded_cards") else "FAIL")
