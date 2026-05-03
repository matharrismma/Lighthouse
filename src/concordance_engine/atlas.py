"""Atlas — the output side of Lighthouse.

Per canonical naming (00_CANON canonical naming, also 03_ARCH/
NAMING_AND_STRUCTURE.md):

  * **Lighthouse** is the project.
  * **Concordance** is the ingestion engine — extracts Seeds,
    aligns to Law, builds truth tables. (This is the codebase's
    `concordance_engine` package.)
  * **Atlas** is the output side — output maps showing lawful paths,
    gates fired, corrective moves the human can take.

The `walkthrough.py` module IS Atlas — it produces the rendered
output a human or agent reads after a packet runs through the four
gates. Atlas re-exports those renderers under the canonical naming
so callers can write code that matches the doctrinal vocabulary:

    from concordance_engine.atlas import (
        render_atlas, render_atlas_compact, render_atlas_html,
    )

    print(render_atlas(record))   # Socratic walkthrough markdown

The underlying functions are unchanged; this module is a vocabulary
alignment, not a fork. Future Atlas-specific outputs (annotated
scaffold maps, lawful-path visualizations beyond the walkthrough)
land here without churning callers of the existing walkthrough API.
"""
from __future__ import annotations

from .walkthrough import (
    render_walkthrough as render_atlas,
    render_walkthrough_compact as render_atlas_compact,
    render_walkthrough_html as render_atlas_html,
)

__all__ = ["render_atlas", "render_atlas_compact", "render_atlas_html"]
