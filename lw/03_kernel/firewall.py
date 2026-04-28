"""
Lighthouse — Physical Firewall Spec (Steward Hardware Gate Pack)

Drop-in gate pack + state machine reference that integrates with the problem engine
WITHOUT changing the kernel verbs (O/B/R/H).

What this file provides:
  - FirewallState: models the physical firewall behavior (intent, timers, budgets)
  - Gate builders: produce Gate definitions compatible with the engine (GDef)
  - Minimal "mail-slot" ledger valve protocol (propose -> verify -> commit) as stubs

Hardware intent:
  - Steward MCU is the final authority for: WIFI_EN, USB_DATA_EN, LORA_TX_WIN, SOC_WAKE, LEDGER_COMMIT
  - Defaults: closed (wifi off, usb data off), LoRa nano only, ledger append-only
  - On-ramps: physical intent opens timed windows
  - Off-ramps: timer expiry, floor threat, gate breach -> close

This is a spec in executable form (simulation). Real firmware implements the same state machine.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
import time

from problem_engine import A, Act, GDef, World

@dataclass
class FirewallState:
    wifi_intent: bool = False
    usb_intent: bool = False
    wifi_until: float = 0.0
    usb_until: float = 0.0
    nano_max_b: int = 1024
    meso_max_b: int = 64 * 1024
    bulk_max_b: int = 1024 * 1024 * 1024
    nano_sent_b: int = 0
    meso_sent_b: int = 0
    bulk_sent_b: int = 0
    safe_shutdown: bool = False
    last_close_reason: str = ""

    def now(self) -> float:
        return time.time()

    def wifi_open(self) -> bool:
        return self.wifi_until > self.now()

    def usb_open(self) -> bool:
        return self.usb_until > self.now()

    def open_wifi(self, secs: int = 300) -> None:
        self.wifi_intent = True
        self.wifi_until = self.now() + secs

    def open_usb(self, secs: int = 300) -> None:
        self.usb_intent = True
        self.usb_until = self.now() + secs

    def close_all(self, reason: str) -> None:
        self.wifi_intent = False
        self.usb_intent = False
        self.wifi_until = 0.0
        self.usb_until = 0.0
        self.last_close_reason = reason

    def tick(self) -> None:
        if self.wifi_until and self.now() > self.wifi_until:
            self.wifi_intent = False
            self.wifi_until = 0.0
        if self.usb_until and self.now() > self.usb_until:
            self.usb_intent = False
            self.usb_until = 0.0

    def record_send(self, lane: str, nbytes: int) -> None:
        if lane == "nano": self.nano_sent_b += nbytes
        elif lane == "meso": self.meso_sent_b += nbytes
        elif lane == "bulk": self.bulk_sent_b += nbytes

    def budget_ok(self, lane: str, nbytes: int) -> bool:
        if lane == "nano": return (self.nano_sent_b + nbytes) <= self.nano_max_b
        if lane == "meso": return (self.meso_sent_b + nbytes) <= self.meso_max_b
        if lane == "bulk": return (self.bulk_sent_b + nbytes) <= self.bulk_max_b
        return False


@dataclass
class MailSlot:
    proposed: List[Dict[str, Any]] = field(default_factory=list)
    committed: List[Dict[str, Any]] = field(default_factory=list)

    def propose(self, pkt: Dict[str, Any]) -> None:
        self.proposed.append(pkt)

    def verify(self, pkt: Dict[str, Any]) -> bool:
        return True  # stub: plug in checksum / schema registry verification

    def commit(self) -> int:
        n = 0
        keep = []
        for pkt in self.proposed:
            if self.verify(pkt):
                self.committed.append(pkt)
                n += 1
            else:
                keep.append(pkt)
        self.proposed = keep
        return n


def build_firewall_gates(
    fw: FirewallState,
    *,
    require_physical_intent_for_online: bool = True,
    lora_nano_only: bool = True,
    floor_close_on_breach: bool = True,
) -> List[GDef]:
    def _lane_from_act(a: Act) -> str:
        t = (a.t or "")
        if "lane:nano" in t: return "nano"
        if "lane:meso" in t: return "meso"
        if "lane:bulk" in t: return "bulk"
        return "nano"

    def g_windows(w: World, a: Act) -> Dict[str, bool]:
        fw.tick()
        lane = _lane_from_act(a)
        if not require_physical_intent_for_online:
            return {"WIN": True}
        if lane == "nano": return {"WIN": True}
        if lane == "meso": return {"WIN": fw.usb_open() or fw.wifi_open()}
        if lane == "bulk": return {"WIN": fw.usb_open()}
        return {"WIN": False}

    def g_budget(w: World, a: Act) -> Dict[str, bool]:
        lane = _lane_from_act(a)
        approx = 256 if lane == "nano" else 8192 if lane == "meso" else 1_000_000
        ok = fw.budget_ok(lane, approx)
        if ok: fw.record_send(lane, approx)
        return {"BUD": ok}

    def g_no_radio_open_in_restore(w: World, a: Act) -> Dict[str, bool]:
        lane = _lane_from_act(a)
        if w.m.value == "R" and lane in ("meso", "bulk"):
            return {"NOR": False}
        return {"NOR": True}

    def g_floor_close(w: World, a: Act) -> Dict[str, bool]:
        if not floor_close_on_breach:
            return {"CLS": True}
        pr = w.ru.pr
        if w.rs.get(pr, 0.0) < w.ru.fl.get(pr, 0.0):
            fw.close_all("floor_breach")
        return {"CLS": True}

    gates = [GDef("FW_WIN", g_windows), GDef("FW_BUD", g_budget)]
    if lora_nano_only:
        gates.append(GDef("FW_NOR", g_no_radio_open_in_restore))
    gates.append(GDef("FW_CLS", g_floor_close))
    return gates


def install_firewall_pack(world: World, fw: FirewallState) -> None:
    world.ru.g.extend(build_firewall_gates(fw))
