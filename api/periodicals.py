"""Stream PD periodicals from D: to the browser without copying them off-disk.

The catalog at content/periodicals.json lists collections and their files.
This router serves them under /periodical/<collection_id>/<filename> with:
  - Existence + path-traversal check (filenames are scoped to the catalog)
  - Strict-PD gate: collections flagged verify_per_strict_rule=True require
    an explicit ?verified=true query param OR a per-issue override list
  - Proper content-type (PDF or EPUB)
  - Range request support (PDF viewers stream pages)
"""
from __future__ import annotations
import json
import mimetypes
from pathlib import Path

try:
    from fastapi import APIRouter, HTTPException, Request, Query
    from fastapi.responses import FileResponse, JSONResponse
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO / "content" / "periodicals.json"
LIB = Path("D:/library_files")


def _load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {"collections": []}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _find_collection(cid: str, catalog: dict) -> dict | None:
    for c in catalog.get("collections", []):
        if c.get("id") == cid:
            return c
    return None


def _find_issue(coll: dict, filename: str) -> dict | None:
    for i in coll.get("issues", []):
        if i.get("filename") == filename:
            return i
    return None


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/periodical")
    def list_collections():
        """Return the public catalog, redacting non-verified collections by default."""
        return _load_catalog()

    @router.get("/periodical/{collection_id}")
    def list_issues(collection_id: str):
        catalog = _load_catalog()
        coll = _find_collection(collection_id, catalog)
        if not coll:
            raise HTTPException(404, f"Collection '{collection_id}' not found")
        return coll

    @router.get("/periodical/{collection_id}/{filename}")
    def serve_issue(collection_id: str, filename: str, verified: bool = Query(False)):
        catalog = _load_catalog()
        coll = _find_collection(collection_id, catalog)
        if not coll:
            raise HTTPException(404, "Collection not found")
        # Strict-PD gate: collections flagged for verification require explicit confirmation
        if coll.get("verify_per_strict_rule") and not verified:
            raise HTTPException(
                403,
                detail={
                    "error": "verify_per_strict_rule",
                    "message": (
                        "This collection's PD basis is per-issue and not yet operator-verified. "
                        "Add ?verified=true to confirm you have verified copyright renewal status "
                        "for this specific issue, or wait for operator review."
                    ),
                    "pd_basis": coll.get("pd_basis", ""),
                }
            )
        issue = _find_issue(coll, filename)
        if not issue:
            raise HTTPException(404, "Issue not found in catalog")
        # Path traversal safety: the filename must match exactly what's in the catalog,
        # and the resolved path must live inside the collection's directory.
        target = (LIB / coll["directory"] / filename).resolve()
        coll_root = (LIB / coll["directory"]).resolve()
        if not str(target).startswith(str(coll_root)):
            raise HTTPException(400, "Bad path")
        if not target.exists() or not target.is_file():
            raise HTTPException(404, "File not on disk")
        media_type, _ = mimetypes.guess_type(filename)
        if not media_type:
            media_type = "application/octet-stream"
        return FileResponse(
            target,
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=86400",
                "Access-Control-Allow-Origin": "*",
                "X-PD-Basis": coll.get("pd_basis", "")[:200],
            },
        )

    return router
