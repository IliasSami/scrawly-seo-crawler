"""Client for the Scrawly Connector WordPress plugin.

Exposes the same method surface as `WPClient` (get_post_meta / update_post_meta /
resolve_post_id / detect_seo_plugins / redirects) so `WPFixer` can use it
unchanged — but authenticates with the plugin's connection key (X-Scrawly-Key)
instead of Application Passwords, and lets the plugin map logical SEO fields to
the active plugin's meta keys server-side.

Uses the `?rest_route=` REST form so it works on any site regardless of whether
pretty permalinks are enabled.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from sentinelseo.wp.client import WPConflictError


def _route(path: str) -> str:
    return f"/scrawly/v1{path}"


class ScrawlyConnectorClient:
    def __init__(self, base_url: str, connection_key: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Scrawly-Key": connection_key},
            timeout=15.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def _get(self, path: str) -> httpx.Response:
        return self.client.get("/", params={"rest_route": _route(path)})

    def _post(self, path: str, json: Dict[str, Any]) -> httpx.Response:
        return self.client.post("/", params={"rest_route": _route(path)}, json=json)

    def _delete(self, path: str) -> httpx.Response:
        return self.client.delete("/", params={"rest_route": _route(path)})

    def status(self) -> Dict[str, Any]:
        resp = self._get("/status")
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
        return data

    def detect_seo_plugins(self) -> str:
        try:
            sp = self.status().get("seo_plugin", "none")
        except Exception:
            sp = "none"
        if sp == "both":
            raise WPConflictError("Both Yoast and RankMath active. Write refused (V06).")
        return "connector"

    def resolve_post_id(self, url: str) -> Optional[int]:
        resp = self._post("/resolve", {"url": url})
        resp.raise_for_status()
        pid = resp.json().get("post_id")
        return int(pid) if pid else None

    def get_post_meta(self, post_id: int) -> Dict[str, Any]:
        resp = self._get(f"/post-meta/{post_id}")
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
        return data

    def update_post_meta(self, post_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._post(f"/post-meta/{post_id}", payload)
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
        return data

    def get_redirects(self) -> List[Dict[str, Any]]:
        resp = self._get("/redirects")
        resp.raise_for_status()
        items: List[Dict[str, Any]] = resp.json().get("items", [])
        return items

    def create_redirect(
        self, source_url: str, target_url: str, match_type: str = "url"
    ) -> Dict[str, Any]:
        resp = self._post(
            "/redirects", {"source": source_url, "target": target_url, "code": 301}
        )
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
        return data

    def delete_redirect(self, redirect_id: int) -> bool:
        resp = self._delete(f"/redirects/{redirect_id}")
        resp.raise_for_status()
        return True
