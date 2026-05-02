# Frozen reference — see top-level src/

This subtree is a frozen Apr-27 snapshot of the engine. The active engine has
moved to `<repo>/src/concordance_engine/` at the top level.

If you came here looking for the engine, the source you want is one level up:

    cd ../../../../              # back to repo root
    cat src/concordance_engine/...

The Python package files in this subtree have been emptied to prevent imports
from accidentally resolving here. Delete this directory entirely once you've
confirmed nothing in your tooling depends on it.
