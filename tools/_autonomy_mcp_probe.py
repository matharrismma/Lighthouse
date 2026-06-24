"""Confirm the MCP `autonomy` tool is live via a FRESH /mcp session."""
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
        "params": {"name": "autonomy", "arguments": {
            "reference": "reach the goal", "errors": [5, 3, 1],
            "action": "publish to the public site"}}})
    obj = parse(r)
    txt = obj["result"]["content"][0]["text"]
    d = json.loads(txt)
    print("decision:", d.get("decision"))
    print("reason:", (d.get("reason") or "")[:60])
    print("authorization.requires_authority:", (d.get("authorization") or {}).get("requires_authority"))
    ok = d.get("decision") == "continue" and (d.get("authorization") or {}).get("requires_authority") is True
    print("MCP autonomy tool:", "PASS" if ok else "FAIL")
