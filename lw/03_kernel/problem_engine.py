"""
Lighthouse — Problem Engine (Universal Reference Implementation)

Core loop:
  Problem seed -> Scripture keys (anchors/directives) -> Kernel routes 4 actions -> Ledger packets.
Domain adapters map the kernel to any context without changing the verbs.
Physical firewalls are modeled as constraints + gate tests that hardware could enforce.

Vocabulary (no new nouns):
  Vessel, World, Action, Rules, Gates, Adapter, Solver, Ledger
"""

import json, uuid, hashlib, random, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable

# --------------------------
# Tiny keys (compressed)
# --------------------------

class M(str, Enum):  # mode
    R="R"  # restore
    N="N"  # normal

class A(str, Enum):  # action kind (the 4 actions)
    R="R"  # reserve (firstfruits / storehouse)
    B="B"  # build (one unit)
    O="O"  # open (new vessel / new lane)
    H="H"  # hold

# Optional "innovation" can be represented as Reserve into a separate pool, without adding a new verb.
# If you want explicit INNOV later, add A.I with zero architectural change.

@dataclass(frozen=True)
class Act:
    k: A
    i: Optional[int] = None   # vessel index (for build)
    x: float = 0.0            # amount (for reserve)
    t: str = ""               # tag (debug/telemetry)

@dataclass
class Vessel:
    id: int
    u: int = 0         # units built in vessel
    m: bool = False    # mature

    def up(self, span: int) -> None:
        if (not self.m) and self.u >= span:
            self.m = True

# --------------------------
# Problem seed (universal)
# --------------------------

@dataclass(frozen=True)
class PSeed:
    # identity: freeform (name, jurisdiction, etc.)
    id: Dict[str, Any] = field(default_factory=dict)
    ph: str = "S"  # phase: S=Setup, P=Positioning, C=Conversion (short keys)
    fl: Dict[str, float] = field(default_factory=dict)  # floors (cash/reserve/etc.)
    cx: Dict[str, Any] = field(default_factory=dict)    # constraints (quarantine, span, firewall, etc.)
    st: Dict[str, Any] = field(default_factory=dict)    # initial state hints (optional)

# --------------------------
# Rules + Gates (universal)
# --------------------------

RuleTest = Callable[['World'], Tuple[bool, Dict[str, bool]]]
RuleFix  = Callable[['World'], Optional[Act]]
GateTest = Callable[['World', Act], Dict[str, bool]]

@dataclass
class RDef:
    n: str
    t: RuleTest
    f: RuleFix

@dataclass
class GDef:
    n: str
    t: GateTest

@dataclass
class Seed:
    # time
    Y: int = 40
    rng: int = 7

    # governance
    Q: int = 2          # quarantine pass threshold (count of True)
    IV: int = 3         # init vessels
    SP: int = 12        # span to maturity (12:1)
    MC: int = 3         # min mature vessels

    # allocation
    FF: float = 0.10    # firstfruits reserve rate
    IN: float = 0.10    # innovation rate (kept here; adapters may use it)

    # resources
    pr: str = "cash"
    fl: Dict[str, float] = field(default_factory=lambda: {"cash": 2_000_000})
    shf: float = 5_000_000  # storehouse floor

    # registries (filled if empty)
    r: List[RDef] = field(default_factory=list)
    g: List[GDef] = field(default_factory=list)

# --------------------------
# Scripture keys (no verse text)
# --------------------------

@dataclass(frozen=True)
class Anch:
    k: str   # ultra-short ref key, e.g., "PR4:23", "GN41", "EX18", "JN15:2"
    p: str   # principle key, e.g., "GUARD", "STORE", "DELEGATE", "PRUNE"

@dataclass(frozen=True)
class Sol:
    a: List[Anch] = field(default_factory=list)      # anchors
    d: List[str]  = field(default_factory=list)      # directives (short), e.g., ["FLOOR", "FF", "SPAN", "PRUNE"]

class Solver:
    """
    Policy compiler:
      classify -> emit (anchors, directives)
    Directives must map to existing kernel primitives (rules/gates/actions). No new verbs.
    """
    def __init__(self, pack: str = "NIV"):
        self.pack = pack

    def cls(self, ps: PSeed, w: 'World') -> List[str]:
        dom = []
        # floors breached -> stability
        if w.m == M.R: dom.append("STAB")
        # low storehouse vs desired reserve floor
        rfl = ps.fl.get("res", w.ru.shf)
        if w.sh < rfl: dom.append("STORE")
        # capacity formation
        if w.cm < ps.cx.get("mc", w.ru.MC): dom.append("GOV")
        # stuckness -> prune
        if w.ne > 0: dom.append("PRUNE")
        return dom[:3]

    def sol(self, ps: PSeed, w: 'World') -> Sol:
        dom = self.cls(ps, w)
        a: List[Anch] = []
        d: List[str] = []
        for x in dom:
            if x == "STAB":
                a.append(Anch("PR4:23","GUARD")); d += ["FLOOR","QUAR"]
            elif x == "STORE":
                a.append(Anch("GN41","STORE")); d += ["FF"]
            elif x == "GOV":
                a.append(Anch("EX18","DELEGATE")); d += ["SPAN"]
            elif x == "PRUNE":
                a.append(Anch("JN15:2","PRUNE")); d += ["PRUNE"]
        # de-dup while preserving order
        d2=[]
        for k in d:
            if k not in d2: d2.append(k)
        return Sol(a=a, d=d2)

# --------------------------
# Ledger (append-only)
# --------------------------

def _cjson(o: Any) -> str:
    return json.dumps(o, sort_keys=True, separators=(",",":"), ensure_ascii=False)

def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _uid() -> str:
    return str(uuid.uuid4())

@dataclass
class Ledger:
    kv: str = "PCK_best"
    e: List[Dict[str, Any]] = field(default_factory=list)

    def emit(self, pt: str, p: Dict[str, Any]) -> None:
        pkt = {"pt": pt, "id": _uid(), "kv": self.kv, **p}
        pkt["cs"] = _sha(_cjson({k:v for k,v in pkt.items() if k!="cs"}))
        self.e.append(pkt)

    def jsonl(self) -> str:
        return "\n".join(_cjson(x) for x in self.e)

# --------------------------
# Adapter (domain mapping)
# --------------------------

class Ad:
    def cost(self, w:'World', a:Act) -> float: raise NotImplementedError
    def dyn(self,  w:'World') -> Dict[str, Any]: raise NotImplementedError
    def apply(self,w:'World', a:Act) -> None: raise NotImplementedError
    def msr(self,  w:'World') -> Dict[str, Any]: return {}

# Example domain adapter (resource allocation: money -> build units -> surplus)
class ExampleAdapter(Ad):
    def __init__(self, seed_in: float, cost_u: float, surp_u: float, shock_n:int, shock_i:float, fail:float, rng:int):
        self.SI=seed_in; self.C=cost_u; self.SU=surp_u
        self.SN=max(1, shock_n); self.SI2=shock_i; self.F=fail
        self.R = random.Random(rng)

    def cost(self, w:'World', a:Act) -> float:
        if a.k == A.B: return self.C
        if a.k == A.R: return a.x
        return 0.0

    def dyn(self, w:'World') -> Dict[str, Any]:
        sh_in  = (self.R.random() < 1/self.SN)
        sh_sur = (self.R.random() < 1/self.SN)
        infl = self.SI*(1-self.SI2) if sh_in else self.SI
        w.rs[w.ru.pr] += infl
        sur = w.ut*self.SU
        sur *= (1-self.SI2) if sh_sur else 1.0
        w.rs[w.ru.pr] += sur
        pruned=False
        if self.F and w.v:
            b=len(w.v)
            w.v = [x for x in w.v if self.R.random() > self.F]
            if not w.v: w.bs(1)
            pruned = (len(w.v)!=b)
        return {"in": infl, "su": sur, "sh_in": sh_in, "sh_su": sh_sur, "pr": pruned}

    def apply(self, w:'World', a:Act) -> None:
        if a.k == A.O:
            w.ov()
        elif a.k == A.B and a.i is not None:
            if 0 <= a.i < len(w.v):
                w.v[a.i].u += 1
                w.v[a.i].up(w.ru.SP)
                w.rs[w.ru.pr] -= self.C
        elif a.k == A.R:
            y = min(a.x, w.hr())
            w.rs[w.ru.pr] -= y
            w.sh += y
        # HOLD -> no-op

    def msr(self, w:'World') -> Dict[str, Any]:
        return {"ut": w.ut, "v": len(w.v), "cm": w.cm, "on": w.on}

# --------------------------
# World
# --------------------------

@dataclass
class World:
    ru: Seed
    ad: Ad
    rs: Dict[str, float] = field(default_factory=dict)  # resources
    sh: float = 0.0     # storehouse
    tp: float = 0.0     # tests pool (optional; adapters may use)
    v:  List[Vessel] = field(default_factory=list)
    m:  M = M.R
    t:  int = 0
    ne: int = 0         # never events (gate denies)
    a:  Optional[Act] = None  # temp for gates

    @property
    def ut(self) -> int:  # units total
        return sum(x.u for x in self.v)

    @property
    def cm(self) -> int:  # cap/mature count
        return sum(1 for x in self.v if x.m)

    @property
    def on(self) -> int:  # open count
        return sum(1 for x in self.v if not x.m)

    def hr(self) -> float:
        return max(0.0, self.rs[self.ru.pr] - self.ru.fl[self.ru.pr])

    def bs(self, n:int) -> None:
        s=len(self.v)
        for i in range(n):
            self.v.append(Vessel(id=s+i+1))

    def ov(self) -> None:
        self.v.append(Vessel(id=len(self.v)+1))

    def pk(self) -> Optional[int]:
        c=[(i,x.u) for i,x in enumerate(self.v) if not x.m]
        c.sort(key=lambda z:z[1], reverse=True)
        return c[0][0] if c else None

# --------------------------
# Kernel (Waymaker)
# --------------------------

class K:
    def __init__(self, ru:Seed, ad:Ad, ps:Optional[PSeed]=None, lg:Optional[Ledger]=None):
        self.ru=ru; self.ad=ad; self.ps=ps; self.lg=lg
        self.sv = Solver(ps.id.get("pack","NIV") if ps else "NIV") if ps else None
        if not self.ru.r: self.ru.r = self._def_rules()
        if not self.ru.g: self.ru.g = self._def_gates()

    # --- default rules (stability first) ---
    def _def_rules(self) -> List[RDef]:
        ru=self.ru
        def liq(w:World): 
            ok = w.rs[ru.pr] >= ru.fl[ru.pr]
            return ok, {"L": ok}
        def liq_fix(w:World): 
            return None  # liquidity restore is adapter/domain-specific (e.g., stop spending)
        def sh(w:World):
            ok = w.sh >= ru.shf
            return ok, {"S": ok}
        def sh_fix(w:World):
            y = min(500_000, w.hr())
            return Act(A.R, x=y, t="res") if y>0 else None
        def mc(w:World):
            ok = w.cm >= ru.MC
            return ok, {"M": ok}
        def mc_fix(w:World):
            i=w.pk()
            if i is None: return None
            if w.hr() >= w.ad.cost(w, Act(A.B)): return Act(A.B, i=i, t="b")
            return None
        return [
            RDef("L", liq, liq_fix),
            RDef("M", mc,  mc_fix),
            RDef("S", sh,  sh_fix),
        ]

    # --- default gates (quarantine) ---
    def _def_gates(self) -> List[GDef]:
        ru=self.ru
        def floor_cash(w:World, a:Act) -> Dict[str,bool]:
            spend = w.ad.cost(w,a)
            return {"F": (w.rs[ru.pr]-spend) >= ru.fl[ru.pr]}
        def no_open_restore(w:World, a:Act) -> Dict[str,bool]:
            return {"NR": not (w.m==M.R and a.k==A.O)}
        def span_ok(_w:World, _a:Act) -> Dict[str,bool]:
            return {"SP": True}  # span is enforced by Vessel.up()
        return [GDef("F", floor_cash), GDef("NR", no_open_restore), GDef("SP", span_ok)]

    # --- mode determination ---
    def _mode(self, w:World) -> List[Dict[str,Any]]:
        rep=[]
        bad=False
        for r in self.ru.r:
            ok, d = r.t(w)
            rep.append({"n": r.n, "ok": ok, "d": d})
            if not ok: bad=True
        w.m = M.R if bad else M.N
        return rep

    # --- routing (4 actions) ---
    def route(self, w:World) -> Tuple[Act, Optional[Sol], List[Dict[str,Any]]]:
        if len(w.v) < self.ru.IV:
            return Act(A.O, t="boot"), None, []

        rep = self._mode(w)
        sol = self.sv.sol(self.ps, w) if self.sv else None

        # Restore path: apply first available rule fix
        # (Scripture can *annotate* restore, but restore actions come from rules.)
        if w.m == M.R:
            for r in self.ru.r:
                ok,_ = r.t(w)
                if not ok:
                    fx = r.f(w)
                    if fx: return fx, sol, rep
            return Act(A.H, t="rh"), sol, rep

        # Normal path: Scripture may steer allocation (e.g., FIRSTFRUITS) without adding new verbs.
        if sol and ("FF" in sol.d) and w.hr() > 0 and w.sh < self.ru.shf:
            return Act(A.R, x=w.hr()*self.ru.FF, t="ff"), sol, rep

        i = w.pk()
        if i is not None and w.hr() >= w.ad.cost(w, Act(A.B)):
            return Act(A.B, i=i, t="b"), sol, rep
        if w.hr() > 0 and w.sh < self.ru.shf:
            return Act(A.R, x=w.hr()*self.ru.FF, t="ff"), sol, rep
        return Act(A.H, t="h"), sol, rep

    # --- gate admit ---
    def admit(self, w:World, a:Act) -> Dict[str,Any]:
        w.a=a
        rep=[]
        trues=0
        for g in self.ru.g:
            d=g.t(w,a)
            ok = all(d.values())
            rep.append({"n": g.n, "ok": ok, "d": d})
            if ok: trues += 1
        ok = (trues >= self.ru.Q)
        if not ok: w.ne += 1
        w.a=None
        return {"ok": ok, "rep": rep}

    # --- tick ---
    def tick(self, w:World) -> None:
        sh = w.ad.dyn(w)
        a, sol, mr = self.route(w)
        gate = self.admit(w,a)
        if gate["ok"]:
            w.ad.apply(w,a)
        if self.lg:
            self.lg.emit("t", {
                "t": w.t,
                "m": w.m.value,
                "a": a.k.value,
                "i": a.i,
                "x": round(a.x,2),
                "tag": a.t,
                "rs": {self.ru.pr: round(w.rs[self.ru.pr],2)},
                "sh": round(w.sh,2),
                "tp": round(w.tp,2),
                "v": len(w.v),
                "cm": w.cm,
                "ut": w.ut,
                "ne": w.ne,
                "gate": gate,
                "dyn": sh,
                "mr": mr,
                "sol": None if not sol else {"a":[{"k":q.k,"p":q.p} for q in sol.a], "d": sol.d},
                "msr": w.ad.msr(w),
            })

    def run(self, start_mult: float = 2.5) -> World:
        w = World(ru=self.ru, ad=self.ad, rs={self.ru.pr: self.ru.fl[self.ru.pr]*start_mult})
        w.bs(self.ru.IV)
        for t in range(1, self.ru.Y+1):
            w.t=t
            self.tick(w)
        return w

# --------------------------
# Physical firewall modeling (software side)
# --------------------------
# Hardware enforcement is done by Steward MCU + switches.
# In software, we represent the firewall as:
#   - constraints in PSeed.cx
#   - gate tests that require an "intent" flag + budgets/windows
# This stays universal and does NOT create new kernel verbs.

@dataclass
class FW:
    # Intent must be physical in hardware; in simulation we model it as a boolean.
    wifi: bool = False
    usb_data: bool = False
    # Budgeting (LEAN): allow only nano over LoRa unless fat pipe.
    nano_max_b: int = 1024
    meso_max_b: int = 1024*64
    bulk_max_b: int = 1024*1024
    # Window end timestamps (seconds since epoch); 0 means closed.
    wifi_until: float = 0.0
    usb_until: float = 0.0

    def open_wifi(self, secs:int=300):
        self.wifi=True; self.wifi_until=time.time()+secs

    def open_usb(self, secs:int=300):
        self.usb_data=True; self.usb_until=time.time()+secs

    def tick(self):
        now=time.time()
        if self.wifi and now>self.wifi_until: self.wifi=False
        if self.usb_data and now>self.usb_until: self.usb_data=False

# --------------------------
# Demo runner
# --------------------------

def demo():
    ru = Seed()
    ps = PSeed(
        id={"name": "Example Domain"},
        ph="S",
        fl={"cash": ru.fl["cash"], "res": 150_000_000},
        cx={"mc": ru.MC, "span": ru.SP, "ff": ru.FF, "in": ru.IN, "firewall": True},
    )
    ad = ExampleAdapter(seed_in=2_000_000, cost_u=750_000, surp_u=120_000, shock_n=5, shock_i=0.3, fail=0.05, rng=ru.rng)
    lg = Ledger(kv="lighthouse_demo")
    k = K(ru, ad, ps, lg)
    w = k.run()
    print("Final:", {"ut": w.ut, "v": len(w.v), "cash": round(w.rs[ru.pr],2), "sh": round(w.sh,2), "cm": w.cm, "ne": w.ne})
    print("Ledger lines:", len(lg.e))
    for ln in lg.jsonl().splitlines()[:2]:
        print(ln)

if __name__ == "__main__":
    demo()