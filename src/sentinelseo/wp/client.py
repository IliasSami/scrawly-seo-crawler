import os
from typing import Any, Dict, Optional

import httpx
from cryptography.fernet import Fernet


class WPAuthError(Exception):
    pass


class WPConflictError(Exception):
    pass


class WPClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        encrypted_app_password: str,
        auth_mode: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self._encrypted_app_password = encrypted_app_password

        key = os.getenv("SCRAWLY_ENCRYPTION_KEY")
        if not key:
            raise ValueError("SCRAWLY_ENCRYPTION_KEY environment variable is not set.")

        f = Fernet(key.encode())
        self._app_password = f.decrypt(self._encrypted_app_password.encode()).decode()

        # Auth: "basic" (Application Passwords) or "jwt" (JWT Authentication plugin).
        self.auth_mode = auth_mode or os.getenv("SCRAWLY_WP_AUTH", "basic")
        if self.auth_mode == "jwt":
            token = self._get_jwt_token(self.username, self._app_password)
            self.client = httpx.Client(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
        else:
            self.client = httpx.Client(
                base_url=self.base_url,
                auth=(self.username, self._app_password),
                timeout=10.0,
            )
        self._active_seo_plugin: Optional[str] = None

    def _get_jwt_token(self, username: str, password: str) -> str:
        """Exchange username/password for a bearer token (JWT Authentication plugin)."""
        resp = httpx.post(
            f"{self.base_url}/wp-json/jwt-auth/v1/token",
            json={"username": username, "password": password},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise WPAuthError(
                f"JWT token request failed ({resp.status_code}): {resp.text[:200]}"
            )
        token = resp.json().get("token")
        if not token:
            raise WPAuthError("JWT endpoint returned no token.")
        return str(token)

    def close(self) -> None:
        self.client.close()

    def detect_seo_plugins(self) -> str:
        """
        Detects which SEO plugin is active (yoast or rankmath).
        Raises WPConflictError if both are active (Invariant).
        Raises ValueError if neither is active.
        """
        if self._active_seo_plugin:
            return self._active_seo_plugin

        yoast_active = False
        rankmath_active = False

        # Test Yoast endpoint or check active plugins via core REST
        # Fetch active plugins from /wp-json/wp/v2/plugins
        resp = self.client.get("/wp-json/wp/v2/plugins", params={"status": "active"})
        if resp.status_code == 200:
            plugins = resp.json()
            for plugin in plugins:
                if "wordpress-seo" in plugin.get("plugin", ""):
                    yoast_active = True
                elif "seo-by-rank-math" in plugin.get("plugin", ""):
                    rankmath_active = True

        if yoast_active and rankmath_active:
            raise WPConflictError(
                "Both Yoast and RankMath are active. Write refused (Check V06)."
            )

        if yoast_active:
            self._active_seo_plugin = "yoast"
        elif rankmath_active:
            self._active_seo_plugin = "rankmath"
        else:
            # Fallback if the plugins endpoint fails or plugins are named differently
            # For MVP, assume it's an error if we can't detect
            raise ValueError("No supported SEO plugin (Yoast/RankMath) detected.")

        return self._active_seo_plugin

    def resolve_post_id(self, url: str) -> Optional[int]:
        """Resolve a crawled URL to its WordPress post/page id.

        Handles ugly permalinks (`?p=`, `?page_id=`) directly and falls back to a
        slug lookup against the posts then pages REST collections.
        """
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        q = parse_qs(parsed.query)
        for key in ("p", "page_id"):
            if key in q and q[key][0].isdigit():
                return int(q[key][0])

        slug = parsed.path.strip("/").split("/")[-1]
        if not slug:
            return None
        for collection in ("posts", "pages"):
            resp = self.client.get(
                f"/wp-json/wp/v2/{collection}", params={"slug": slug}
            )
            if resp.status_code == 200 and resp.json():
                return int(resp.json()[0]["id"])
        return None

    def get_post_meta(self, post_id: int) -> Dict[str, Any]:
        resp = self.client.get(f"/wp-json/wp/v2/posts/{post_id}")
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
        return data

    def update_post_meta(self, post_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post(f"/wp-json/wp/v2/posts/{post_id}", json=payload)
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
        return data

    # Redirection plugin API endpoints usually at /wp-json/redirection/v1/redirect
    def get_redirects(self) -> list[Dict[str, Any]]:
        resp = self.client.get("/wp-json/redirection/v1/redirect")
        if resp.status_code == 404:
            raise ValueError("Redirection plugin is not active or REST API is blocked.")
        resp.raise_for_status()
        items: list[Dict[str, Any]] = resp.json().get("items", [])
        return items

    def create_redirect(
        self, source_url: str, target_url: str, match_type: str = "url"
    ) -> Dict[str, Any]:
        payload = {
            "url": source_url,
            "action_data": {"url": target_url},
            "action_code": 301,
            "action_type": "url",
            "match_type": match_type,
        }
        resp = self.client.post("/wp-json/redirection/v1/redirect", json=payload)
        resp.raise_for_status()
        data: Dict[str, Any] = resp.json()
        return data

    def delete_redirect(self, redirect_id: int) -> bool:
        resp = self.client.post(
            "/wp-json/redirection/v1/bulk/redirect/delete",
            json={"items": [redirect_id]},
        )
        resp.raise_for_status()
        return True
