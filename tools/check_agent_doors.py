#!/usr/bin/env python3
"""Agent-door health check -- are the connections agents use actually open?

The human surfaces have check_surfaces.py. This is the agent-side equivalent: it
exercises the doors an external agent uses and asserts they behave, not just that they
200. A real MCP handshake + tools/list, the conscience denying harm, the manifest, and
-- critically -- that the public /mcp-stats count matches the LIVE tools/list count, so
the front door can never drift out of sync with reality again (the bug this was built
after: mcp.html advertised 86 tools while 134 were exposed).

    python tools/check_agent_doors.py [--base https://narrowhighway.com]

Read-only except /robot/admit, which is a query (asks "is this aligned?"), not an action.
Exits 0 if every door behaves, 1 otherwise.
"""
import argparse
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "nh-agent-door-check/1.0"}


def _mcp_post(base, body, sid=None):
    h = {"Content-Type": "application/json",
         "Accept": "application/json, text/event-stream", **UA}
    if sid:
        h["Mcp-Session-Id"] = sid
    req = urllib.request.Request(base.rstrip("/") + "/mcp/",
                                 data=json.dumps(body).encode(), headers=h)
    r = urllib.request.urlopen(req, timeout=25)
    txt = r.read().decode("utf-8", "replace")
    m = re.search(r"data: (.*)", txt)  # streamable-HTTP wraps JSON in an SSE frame
    data = json.loads(m.group(1)) if m else (json.loads(txt) if txt.strip() else {})
    return r.headers.get("Mcp-Session-Id"), data


def _get(base, path):
    req = urllib.request.Request(base.rstrip("/") + path, headers=UA)
    r = urllib.request.urlopen(req, timeout=20)
    return r.status, json.loads(r.read().decode("utf-8", "replace"))


def _post_json(base, path, body):
    req = urllib.request.Request(base.rstrip("/") + path,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **UA})
    r = urllib.request.urlopen(req, timeout=20)
    return r.status, json.loads(r.read().decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://narrowhighway.com")
    args = ap.parse_args()
    base = args.base
    rows = []
    ok_all = True

    def record(name, ok, note):
        nonlocal ok_all
        ok_all = ok_all and ok
        rows.append((name, "ok " if ok else ">> ", note))

    live_tools = None
    # 1. MCP handshake + tools/list
    try:
        sid, init = _mcp_post(base, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                                "clientInfo": {"name": "doorcheck", "version": "1"}}})
        srv = init.get("result", {}).get("serverInfo", {})
        ok = srv.get("name") == "concordance"
        record("mcp.initialize", ok, "%s v%s" % (srv.get("name"), srv.get("version")))
        try:
            _mcp_post(base, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
        except Exception:
            pass
        _, tl = _mcp_post(base, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid)
        live_tools = len(tl.get("result", {}).get("tools", []))
        record("mcp.tools/list", live_tools and live_tools > 0, "%s tools" % live_tools)
    except Exception as e:  # noqa: BLE001
        record("mcp.handshake", False, type(e).__name__ + ": " + str(e)[:50])

    # 2. The conscience must DENY (never admit) a physical-harm action
    try:
        _, adm = _post_json(base, "/robot/admit",
                            {"visitor_id": "doorcheck-robot", "action_kind": "move_forward",
                             "risk_flags": ["physical_harm_possible"], "escalation_level": 1})
        dec = (adm or {}).get("decision")
        record("robot/admit denies harm", dec is not None and dec != "admit",
               "decision=%s reason=%s" % (dec, (adm or {}).get("reason_code")))
    except Exception as e:  # noqa: BLE001
        record("robot/admit", False, type(e).__name__ + ": " + str(e)[:50])

    # 3. Manifest reachable + non-empty; surface the benchmark so a stale/false
    #    claim is visible in the output (it derives live from the results file).
    try:
        code, mani = _get(base, "/manifest")
        n = len(mani.get("tools", []))
        bench = mani.get("benchmark", {})
        record("/manifest", code == 200 and n > 0,
               "%s tools | benchmark %s (%s domains)" % (n, bench.get("score"), bench.get("domains")))
    except Exception as e:  # noqa: BLE001
        record("/manifest", False, type(e).__name__ + ": " + str(e)[:50])

    # 3b. OpenAI Actions schema reachable (ChatGPT Custom GPT discovery path)
    try:
        code, oa = _get(base, "/openapi-actions.json")
        nop = len(oa.get("paths", {}))
        record("/openapi-actions.json", code == 200 and nop > 0, "%s operations" % nop)
    except Exception as e:  # noqa: BLE001
        record("/openapi-actions.json", False, type(e).__name__ + ": " + str(e)[:50])

    # 4. Public /mcp-stats reachable AND consistent with the LIVE tools/list
    try:
        code, st = _get(base, "/mcp-stats")
        stated = st.get("tools")
        consistent = (live_tools is None) or (stated == live_tools)
        record("/mcp-stats matches live", code == 200 and stated and consistent,
               "stated=%s live=%s%s" % (stated, live_tools,
                                        "" if consistent else "  <-- FRONT DOOR DRIFTED"))
    except Exception as e:  # noqa: BLE001
        record("/mcp-stats", False, type(e).__name__ + ": " + str(e)[:50])

    print("agent door                  status  note")
    print("-" * 60)
    for name, mark, note in rows:
        print("%s%-25s %s" % (mark, name, note))
    print("-" * 60)
    print("AGENT DOORS OK" if ok_all else "AGENT DOOR PROBLEM")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
