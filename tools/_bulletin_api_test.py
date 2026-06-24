"""Live test of the bulletin REST endpoints against the running server."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def post(path, obj):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=25) as r:
        return json.load(r)


pub = post("/bulletin/publish", {"text": "Shelter OPEN at First Baptist, 5th and Main. Bring ID."})
bundle, ref = pub["bundle"], pub["ref"]
key = get("/identity/pubkey")["public_key_b64u"]
print(f"PUBLISH  bytes={pub['bytes']}  ref={ref[:28]}...  ref_short={pub['ref_short']}")

v = post("/bulletin/verify", {"bundle": bundle, "ref": ref, "pubkey": key})
print(f"VERIFY clean    unaltered={v['unaltered']} authentic={v['authentic']}")

t = dict(bundle)
t["text"] = t["text"].replace("First Baptist", "Other Place")   # a relay tampers
vt = post("/bulletin/verify", {"bundle": t, "ref": ref, "pubkey": key})
print(f"VERIFY tampered unaltered={vt['unaltered']} authentic={vt['authentic']}")

ok = v["unaltered"] and v["authentic"] and not vt["unaltered"] and not vt["authentic"]
print("ENDPOINTS PASS — publish + verify + tamper-detection live" if ok else "FAIL")
