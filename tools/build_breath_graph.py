#!/usr/bin/env python3
"""Emit the evidence-labelled graph for THE BREATH visual.

THE BREATH is the brain map with one thing added that is the whole point: every node
and edge carries an EVIDENCE LABEL, so a viewer (human, agent, or a future reader) can
see at a glance what is PROVEN versus what is only RESONANT. We never disguise a felt
likeness as a fact -- the map's honesty is its differentiator (we cannot out-scale a
knowledge graph; we can out-true it).

Evidence is grounded in REAL data, invented nowhere:
  - data/codex/index/connections.json `verified_structural` carries a verdict per
    connection (CONFIRMED = a deterministic verifier confirmed it; CONCORDANT = the
    gathered witnesses agree; MIXED = partial). A connection is itself a node, so its
    verdict tags the edges incident to it.
  - Source roots (the vine's root) are marked `source` -- rendered as a gap, never a node.
  - Everything else is `resonance`: a shared-axis likeness, NOT a verified connection
    (the codex's own honest label).

Output: site/breath-graph.json  (brain fields + node_ev[] + edge_ev[] + an honest breakdown)
Usage:  python tools/build_breath_graph.py
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CM = os.path.join(ROOT, "data", "codex", "coordinate_map.json")
CONN = os.path.join(ROOT, "data", "codex", "index", "connections.json")
OUT = os.path.join(ROOT, "site", "breath-graph.json")
LED = os.path.join(ROOT, "data", "almanac", "resonance_grounding.jsonl")
ENTRIES = os.path.join(ROOT, "data", "almanac", "entries.jsonl")
# Each almanac entry already carries its OWN verdict -- the work is done. Read it.
VERDICT_MAP = {
    "HOLDS": "verified",
    "CONFIRMED": "concordant", "CONCORDANT": "concordant", "STRUCTURAL": "concordant",
    "MIXED": "mixed", "PARTIAL": "mixed",
    "MISMATCH": "retired", "OBSOLETE": "retired", "DEPARTED": "retired", "NON_EXAMPLE": "retired",
    # NONE / DISCOVERED -> left as resonance (genuinely no verdict yet)
}
TREE = {"language": 0, "math": 1, "axis": 2}
ROOTS = ("connection_reality_is_mappable", "teaching_the_true_vine",
         "teaching_the_words_of_christ_are_the_architecture")

# evidence rank: higher wins when an edge touches two differently-graded nodes.
# `retired` ranks below resonance so a proven-FALSE node never lends evidence to an edge.
EV = {"source": 4, "verified": 3, "concordant": 2, "mixed": 1, "resonance": 0, "retired": -1}
VERDICT_TO_EV = {"CONFIRMED": "verified", "CONCORDANT": "concordant", "MIXED": "mixed"}
# the resonance-grounding campaign: a saying that was grounded moves off pure resonance.
GROUND_EV = {"ATTRIBUTED": "concordant", "VERIFIED": "concordant",
             "RETIRED": "retired", "LEFT": "resonance"}


def main():
    cm = json.load(open(CM, encoding="utf-8"))
    nodes = cm["nodes"]
    idx = {n["id"]: i for i, n in enumerate(nodes)}

    # connection_id -> evidence, from the real verified-connections index
    conn_ev = {}
    try:
        cj = json.load(open(CONN, encoding="utf-8"))
        for c in cj.get("verified_structural", []) + cj.get("verified", []):
            cid = c.get("id")
            ev = VERDICT_TO_EV.get((c.get("verdict") or "").upper())
            if cid and ev:
                # keep the strongest if a connection appears twice
                if EV.get(ev, 0) >= EV.get(conn_ev.get(cid, "resonance"), 0):
                    conn_ev[cid] = ev
    except FileNotFoundError:
        pass

    # PRIMARY grounding: each entry's OWN almanac verdict (already computed -- the work
    # is done). This is the source of truth; connections.json is only a fallback for
    # connection_* nodes that are not themselves entries.
    entry_verdict = {}
    try:
        with open(ENTRIES, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    e = json.loads(line)
                    if e.get("id") and e.get("verdict"):
                        entry_verdict[e["id"]] = e["verdict"]
    except FileNotFoundError:
        pass

    # node evidence
    node_ev = []
    for n in nodes:
        nid = n["id"]
        if nid in ROOTS:
            node_ev.append("source")
        elif nid in entry_verdict:
            node_ev.append(VERDICT_MAP.get(entry_verdict[nid], "resonance"))
        elif nid in conn_ev:
            node_ev.append(conn_ev[nid])
        else:
            node_ev.append("resonance")

    # apply the resonance-grounding campaign ledger: a saying we GROUNDED moves off
    # pure resonance (attributed/verified -> concordant), and a saying we proved FALSE
    # is RETIRED -- shown honestly, never hidden. Only resonance nodes are upgraded.
    grounded = {}
    try:
        with open(LED, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    grounded[rec.get("id")] = rec.get("outcome")
    except FileNotFoundError:
        pass
    for i, n in enumerate(nodes):
        g = grounded.get(n["id"])
        if g and node_ev[i] == "resonance":
            node_ev[i] = GROUND_EV.get(g, "resonance")

    x = [round(float(n["x"]), 1) for n in nodes]
    y = [round(float(n["y"]), 1) for n in nodes]
    tree = [TREE.get(n.get("tree"), 2) for n in nodes]
    hue = [int(n.get("hue", 200)) for n in nodes]
    name = [(n.get("title") or n.get("id") or "")[:90] for n in nodes]
    nid = [n["id"] for n in nodes]

    def pairs(key):
        out = []
        for e in cm.get(key, []):
            if len(e) >= 2 and e[0] in idx and e[1] in idx:
                out.append([idx[e[0]], idx[e[1]]])
        return out

    edges = pairs("edges")
    kin = pairs("kin")

    # an edge inherits the STRONGER evidence of its two endpoints: a verified
    # connection node lends its proof to the edges that reach it.
    def edge_ev(a, b):
        ea, eb = node_ev[a], node_ev[b]
        # source is structural, not evidential, for edges -> treat as its other end
        cand = [e for e in (ea, eb) if e != "source"] or ["resonance"]
        return max(cand, key=lambda e: EV.get(e, 0))

    edge_ev_list = [edge_ev(a, b) for a, b in edges]

    deg = [0] * len(nodes)
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
    for i, j in kin:
        deg[i] += 1
        deg[j] += 1
    src = [idx[s] for s in ROOTS if s in idx]

    from collections import Counter
    node_break = dict(Counter(node_ev))
    edge_break = dict(Counter(edge_ev_list))

    out = {
        "meta": {
            "nodes": len(nodes), "edges": len(edges), "kin": len(kin),
            "node_evidence": node_break, "edge_evidence": edge_break,
            "grounded_resonances": len(grounded),
            "legend": {"source": "the root the map points to (rendered as a gap, never a node)",
                       "verified": "a deterministic verifier confirmed it",
                       "concordant": "the gathered witnesses agree / a named source grounds it",
                       "mixed": "partial / qualified",
                       "resonance": "a shared-axis likeness -- NOT a verified connection",
                       "retired": "a saying we tested and it did NOT hold -- shown, not hidden"},
            "note": "THE BREATH -- the engine's real map, every node and edge labelled by "
                    "what backs it. Honest by construction: resonance is never shown as fact.",
        },
        "x": x, "y": y, "tree": tree, "hue": hue, "deg": deg, "name": name, "id": nid,
        "node_ev": node_ev, "edges": edges, "edge_ev": edge_ev_list, "kin": kin, "src": src,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    kb = os.path.getsize(OUT) / 1024
    print("wrote %s (%.0f KB)" % (OUT, kb))
    print("nodes by evidence:", node_break)
    print("edges by evidence:", edge_break)


if __name__ == "__main__":
    main()
