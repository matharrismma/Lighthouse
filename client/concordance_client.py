"""concordance_client — minimal Python client for the live engine.

A single file that wraps the public REST API. Drop it into your project,
import, and call. No dependencies beyond `requests` (or `urllib` if you
pass `use_stdlib=True`).

Usage:

    from concordance_client import Concordance

    c = Concordance()  # defaults to https://narrowhighway.com

    # rehearse a packet, then commit
    packet = {
        "domain": "governance",
        "scope": "adapter",
        "created_epoch": int(time.time()),
        "DECISION_PACKET": {...},
    }
    preview = c.reflect(packet)
    if preview["overall"] == "PASS":
        result = c.submit(packet)
        print(f"Recorded as ledger seq {result['ledger_seq']}")

    # scripture lookups
    verse = c.scripture("Jn3:16")
    word = c.strong("G26")

    # drift / triangulation
    tri = c.triangulate("Jn15:2", claim="branches that don't bear fruit are destroyed",
                        strongs_keys=["G142"])

    # ledger search
    rejects = c.dispatch(overall="REJECT", limit=20)
    stats = c.stats()
    about = c.about()

    # confession
    c.confess(ref_seq=42, confessor="me",
              reason="The earlier scope was too broad",
              amendment="Re-scope to a single team")

License: Apache 2.0 (matches the engine).
Source: https://github.com/matharrismma/Lighthouse
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import quote


class ConcordanceError(Exception):
    """Raised when the engine returns a non-2xx response."""
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


class Concordance:
    """Sync HTTP client for https://narrowhighway.com (or any compatible
    deployment). Thin wrapper — everything is one round-trip."""

    DEFAULT_URL = "https://narrowhighway.com"

    def __init__(self,
                 base_url: str = DEFAULT_URL,
                 api_key: Optional[str] = None,
                 timeout: float = 30.0,
                 use_stdlib: bool = False):
        """
        Args:
            base_url:     Base URL of the deployment. Default narrowhighway.com.
            api_key:      Sent as X-Api-Key header. Required for /validate.
            timeout:      Per-request timeout in seconds.
            use_stdlib:   If True, use urllib instead of requests (no deps).
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._use_stdlib = use_stdlib

    # -- internal HTTP -----------------------------------------------------

    def _request(self, method: str, path: str,
                 params: Optional[Dict[str, Any]] = None,
                 json_body: Optional[Dict[str, Any]] = None,
                 send_api_key: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if send_api_key and self.api_key:
            headers["X-Api-Key"] = self.api_key

        if not self._use_stdlib:
            import requests  # lazy import
            resp = requests.request(
                method, url, params=params, json=json_body,
                headers=headers, timeout=self.timeout,
            )
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                raise ConcordanceError(resp.status_code, body)
            return resp.json()

        # stdlib fallback (no third-party deps)
        from urllib.request import Request, urlopen
        from urllib.parse import urlencode
        from urllib.error import HTTPError

        if params:
            url = f"{url}?{urlencode({k: v for k, v in params.items() if v is not None})}"
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
        req = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8") or "null")
        except HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8") or "null")
            except Exception:
                body = e.reason
            raise ConcordanceError(e.code, body)

    # -- gate-running endpoints --------------------------------------------

    def reflect(self, packet: Dict[str, Any], now_epoch: Optional[int] = None) -> Dict[str, Any]:
        """Rehearse a packet. Same gates as /submit; NOT recorded to ledger."""
        body: Dict[str, Any] = {"packet": packet}
        if now_epoch is not None:
            body["now_epoch"] = now_epoch
        return self._request("POST", "/reflect", json_body=body)

    def submit(self, packet: Dict[str, Any], now_epoch: Optional[int] = None) -> Dict[str, Any]:
        """Public unauthenticated submission. Recorded to ledger."""
        body: Dict[str, Any] = {"packet": packet}
        if now_epoch is not None:
            body["now_epoch"] = now_epoch
        return self._request("POST", "/submit", json_body=body)

    def validate(self, packet: Dict[str, Any],
                 now_epoch: Optional[int] = None,
                 run_verifiers: bool = True) -> Dict[str, Any]:
        """Authenticated submission with strict GOD-gate timing. Requires
        an api_key on the client."""
        if not self.api_key:
            raise ValueError("api_key required for /validate")
        body: Dict[str, Any] = {"packet": packet, "run_verifiers": run_verifiers}
        if now_epoch is not None:
            body["now_epoch"] = now_epoch
        return self._request("POST", "/validate",
                             json_body=body, send_api_key=True)

    # -- confession --------------------------------------------------------

    def confess(self, *, ref_seq: int, confessor: str, reason: str,
                amendment: Optional[str] = None,
                scripture_anchors: Optional[List[str]] = None) -> Dict[str, Any]:
        """Record recognition that a prior packet (at ledger `ref_seq`) was wrong."""
        body: Dict[str, Any] = {
            "ref_seq": ref_seq,
            "confessor": confessor,
            "reason": reason,
        }
        if amendment is not None:
            body["amendment"] = amendment
        if scripture_anchors:
            body["scripture_anchors"] = list(scripture_anchors)
        return self._request("POST", "/confess", json_body=body)

    # -- ledger ------------------------------------------------------------

    def ledger(self, n: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Newest N ledger entries."""
        return self._request("GET", "/ledger",
                             params={"n": n, "offset": offset})

    def ledger_by_id(self, packet_id: str) -> Dict[str, Any]:
        """Every ledger entry for a packet_id."""
        return self._request("GET", f"/ledger/{quote(packet_id, safe='')}")

    def verify_chain(self) -> Dict[str, Any]:
        """Confirm hash-chain integrity end-to-end."""
        return self._request("GET", "/ledger/verify")

    def dispatch(self, *, domain: Optional[str] = None,
                 overall: Optional[str] = None,
                 packet_id: Optional[str] = None,
                 since_epoch: Optional[int] = None,
                 until_epoch: Optional[int] = None,
                 limit: int = 50) -> Dict[str, Any]:
        """Filtered ledger search. AND semantics."""
        params = {
            "domain": domain, "overall": overall, "packet_id": packet_id,
            "since_epoch": since_epoch, "until_epoch": until_epoch,
            "limit": limit,
        }
        return self._request("GET", "/dispatch", params=params)

    def stats(self) -> Dict[str, Any]:
        """Aggregate ledger counts."""
        return self._request("GET", "/stats")

    def about(self) -> Dict[str, Any]:
        """Service metadata: version, engine availability, layer-0 status,
        ledger total, chain validity, license, source."""
        return self._request("GET", "/about")

    # -- scripture / Layer 0 ----------------------------------------------

    def scripture(self, ref: str) -> Dict[str, Any]:
        """Resolve a scripture reference to WEB text."""
        # Use path encoding rather than query so the URL matches /scripture/{ref:path}
        return self._request("GET", f"/scripture/{quote(ref, safe=':')}")

    def strong(self, strongs_num: str) -> Dict[str, Any]:
        """Strong's word study by number (e.g. 'G26', 'H2617')."""
        return self._request("GET", f"/strong/{quote(strongs_num, safe='')}")

    def triangulate(self, ref: str, claim: str,
                    strongs_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Triangulate an interpretation claim against original-language Strong's."""
        body: Dict[str, Any] = {"ref": ref, "claim": claim}
        if strongs_keys:
            body["strongs_keys"] = list(strongs_keys)
        return self._request("POST", "/triangulate", json_body=body)

    # -- meta --------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """Liveness check."""
        return self._request("GET", "/health")

    def llms_txt(self) -> str:
        """Agent-facing service description as plain text."""
        # Direct request without JSON parsing
        if not self._use_stdlib:
            import requests
            r = requests.get(f"{self.base_url}/llms.txt", timeout=self.timeout)
            r.raise_for_status()
            return r.text
        from urllib.request import urlopen
        with urlopen(f"{self.base_url}/llms.txt", timeout=self.timeout) as r:
            return r.read().decode("utf-8")
