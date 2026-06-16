#!/usr/bin/env python3
"""Emit a compact, web-servable graph for the engine "digital brain" visual.

Reads the REAL coordinate map (data/codex/coordinate_map.json, produced by
coordinate_map.py from the almanac entries + their bonds) and writes a small
parallel-array JSON the canvas renderer streams. Nothing invented -- the brain is
the engine's actual structure: two trees from one source (math <-> language),
layered by depth, hued by frequency, wired by concord bonds (the vine) + kin braces.

Output: site/brain-graph.json
  x[],y[]      node positions (from the real projection)
  tree[]       0=language(organic) 1=math(matrix) 2=axis
  hue[]        node colour (frequency)
  deg[]        synapse count (bonds+kin) -> neuron size
  name[]       title (hover)
  edges[[i,j]] concord bonds -- the vine (the paths we follow)
  kin[[i,j]]   structural same-form braces (secondary, drawn faint)
  src[]        the root/source nodes (the brainstem)

Usage:  python tools/build_brain_graph.py   (run coordinate_map.py first)
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "codex", "coordinate_map.json")
OUT = os.path.join(ROOT, "site", "brain-graph.json")
TREE = {"language": 0, "math": 1, "axis": 2}
ROOTS = ("connection_reality_is_mappable", "teaching_the_true_vine",
         "teaching_the_words_of_christ_are_the_architecture")


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    nodes = d["nodes"]
    idx = {n["id"]: i for i, n in enumerate(nodes)}
    x = [round(float(n["x"]), 1) for n in nodes]
    y = [round(float(n["y"]), 1) for n in nodes]
    tree = [TREE.get(n.get("tree"), 2) for n in nodes]
    hue = [int(n.get("hue", 200)) for n in nodes]
    name = [(n.get("title") or n.get("id") or "")[:90] for n in nodes]

    def pairs(key):
        out = []
        for e in d.get(key, []):
            if len(e) >= 2 and e[0] in idx and e[1] in idx:
                out.append([idx[e[0]], idx[e[1]]])
        return out

    edges = pairs("edges")
    kin = pairs("kin")
    deg = [0] * len(nodes)
    for i, j in edges:
        deg[i] += 1
        deg[j] += 1
    for i, j in kin:
        deg[i] += 1
        deg[j] += 1
    src = [idx[s] for s in ROOTS if s in idx]

    out = {
        "meta": {"nodes": len(nodes), "edges": len(edges), "kin": len(kin),
                 "trees": {"0": "language (organic)", "1": "math (matrix)", "2": "axis"},
                 "note": "The engine's real structure -- two trees from one source, "
                         "wired by concord bonds. Built from the almanac; invents nothing."},
        "x": x, "y": y, "tree": tree, "hue": hue, "deg": deg, "name": name,
        "edges": edges, "kin": kin, "src": src,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    kb = os.path.getsize(OUT) / 1024
    print("wrote %s  (%d nodes, %d bonds, %d kin, %d src, %.0f KB)"
          % (OUT, len(nodes), len(edges), len(kin), len(src), kb))


if __name__ == "__main__":
    main()
