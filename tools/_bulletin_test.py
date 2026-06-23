"""Offline integrity test for api/bulletin.py — publish, then prove tamper /
wrong-ref / wrong-key are all caught. Run on the droplet with the venv python."""
import copy
from api import bulletin

p = bulletin.publish("Water point OPEN at the school gym, north entrance. Boil 1 min before drinking.")
bundle, ref = p["bundle"], p["ref"]
own = bundle["_instance_pubkey"]
print(f"published: bytes={p['bytes']}  ref={ref}  ref_short={p['ref_short']}")

v = bulletin.verify(bundle, ref=ref, pubkey=own)
print(f"CLEAN     unaltered={v['unaltered']} authentic={v['authentic']}  ({v['detail'][:90]})")

t = copy.deepcopy(bundle)
t["text"] = t["text"].replace("north", "south")          # a malicious relay edits it
vt = bulletin.verify(t, ref=ref, pubkey=own)
print(f"TAMPERED  unaltered={vt['unaltered']} authentic={vt['authentic']}  ({vt['detail'][:90]})")

vr = bulletin.verify(bundle, ref="nh1:" + ("0" * 64), pubkey=own)
print(f"WRONG-REF unaltered={vr['unaltered']} authentic={vr['authentic']}")

vp = bulletin.verify(bundle, ref=ref, pubkey=("AAAA" + own[4:]))  # claim a different issuer
print(f"WRONG-KEY unaltered={vp['unaltered']} authentic={vp['authentic']}")

ok = (v["unaltered"] and v["authentic"]
      and not vt["unaltered"] and not vt["authentic"]
      and not vr["unaltered"]
      and not vp["authentic"])
print("VERDICT:", "PASS — tamper, wrong-ref, and wrong-key are all caught offline"
      if ok else "FAIL")
