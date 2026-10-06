from typing import Any, Dict


class WPFixer:
    # `client` is a WPClient or a ScrawlyConnectorClient — both expose the same
    # get/update-post-meta + redirect surface (duck-typed).
    def __init__(self, client: Any):
        self.client = client
        self.seo_plugin = self.client.detect_seo_plugins()

    def _get_meta_key(self, field: str) -> str:
        # Map logical field to Yoast/RankMath meta key
        mapping = {
            "yoast": {
                "title": "_yoast_wpseo_title",
                "meta_desc": "_yoast_wpseo_metadesc",
                "noindex": "_yoast_wpseo_meta-robots-noindex",
                "nofollow": "_yoast_wpseo_meta-robots-nofollow",
                "canonical": "_yoast_wpseo_canonical",
            },
            "rankmath": {
                "title": "rank_math_title",
                "meta_desc": "rank_math_description",
                "noindex": "rank_math_robots",
                "canonical": "rank_math_canonical_url",
            },
            # Connector plugin maps logical fields to plugin keys server-side.
            "connector": {
                "title": "title",
                "meta_desc": "meta_desc",
                "noindex": "robots",
                "canonical": "canonical",
            },
        }

        try:
            return mapping[self.seo_plugin][field]
        except KeyError:
            raise NotImplementedError(
                f"Field {field} mapping not implemented for {self.seo_plugin}"
            ) from None

    def apply_meta_fix(
        self, post_id: int, field: str, new_value: Any
    ) -> Dict[str, Any]:
        """
        Applies a meta field update for title, description, or canonical.
        Returns a rollback token dictionary containing the exact before state.
        """
        meta_key = self._get_meta_key(field)

        # 1. Fetch before state
        current_data = self.client.get_post_meta(post_id)
        current_meta = current_data.get("meta", {})

        before_val = current_meta.get(meta_key, "")

        # 2. Check for idempotency
        if before_val == new_value:
            # Already in desired state, no write needed.
            return {
                "post_id": post_id,
                "field": field,
                "meta_key": meta_key,
                "before_val": before_val,
                "action": "none_idempotent",
            }

        # 3. Apply fix
        payload = {"meta": {meta_key: new_value}}
        self.client.update_post_meta(post_id, payload)

        # 4. Return rollback token
        return {
            "post_id": post_id,
            "field": field,
            "meta_key": meta_key,
            "before_val": before_val,
            "action": "updated",
        }

    def revert_meta_fix(self, token: Dict[str, Any]) -> bool:
        if token.get("action") != "updated":
            return True  # Nothing to revert

        post_id = token["post_id"]
        meta_key = token["meta_key"]
        before_val = token["before_val"]

        payload = {"meta": {meta_key: before_val}}
        self.client.update_post_meta(post_id, payload)
        return True

    def create_redirect(self, source_url: str, target_url: str) -> Dict[str, Any]:
        # 1. Check idempotency
        existing = self.client.get_redirects()
        for r in existing:
            if r.get("url") == source_url and r.get("action_data") == target_url:
                return {
                    "source_url": source_url,
                    "target_url": target_url,
                    "redirect_id": r.get("id"),
                    "action": "none_idempotent",
                }

        # 2. Apply fix
        result = self.client.create_redirect(source_url, target_url)
        redirect_id = result.get("id")

        # 3. Return rollback token
        return {
            "source_url": source_url,
            "target_url": target_url,
            "redirect_id": redirect_id,
            "action": "created",
        }

    def revert_redirect(self, token: Dict[str, Any]) -> bool:
        if token.get("action") != "created":
            return True

        redirect_id = token["redirect_id"]
        if redirect_id:
            self.client.delete_redirect(redirect_id)
        return True

    # --- I2-ordered flow: snapshot (read-only) then commit_write (mutate) ---
    # The caller persists the snapshot to the `fix` table BEFORE calling
    # commit_write, so a crash mid-write still leaves a valid rollback record.
    def snapshot(self, fix_type: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Capture before-state WITHOUT mutating anything (Invariant I2)."""
        if args.get("tier") == "FLAG":
            raise ValueError("Cannot auto-fix a FLAG-tier issue (WPFixer gate).")
        if fix_type == "meta":
            meta_key = self._get_meta_key(args["field"])
            current = self.client.get_post_meta(args["post_id"])
            before_val = current.get("meta", {}).get(meta_key, "")
            return {
                "fix_type": "meta",
                "post_id": args["post_id"],
                "field": args["field"],
                "meta_key": meta_key,
                "before_val": before_val,
                "new_value": args["new_value"],
                "action": "pending",
            }
        elif fix_type == "redirect":
            existing_id = None
            for r in self.client.get_redirects():
                if r.get("url") == args["source_url"]:
                    existing_id = r.get("id")
                    break
            return {
                "fix_type": "redirect",
                "source_url": args["source_url"],
                "target_url": args["target_url"],
                "existing_id": existing_id,
                "action": "pending",
            }
        else:
            raise ValueError(f"Unknown fix type {fix_type}")

    def commit_write(self, before: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the mutation using a previously captured snapshot.

        Returns the finalized rollback token (the snapshot plus the resulting
        `action` and any new ids). Idempotent when the target already matches.
        """
        fix_type = before["fix_type"]
        if fix_type == "meta":
            if before["before_val"] == before["new_value"]:
                return {**before, "action": "none_idempotent"}
            self.client.update_post_meta(
                before["post_id"], {"meta": {before["meta_key"]: before["new_value"]}}
            )
            return {**before, "action": "updated"}
        elif fix_type == "redirect":
            if before.get("existing_id"):
                return {**before, "redirect_id": before["existing_id"],
                        "action": "none_idempotent"}
            result = self.client.create_redirect(
                before["source_url"], before["target_url"]
            )
            return {**before, "redirect_id": result.get("id"), "action": "created"}
        else:
            raise ValueError(f"Unknown fix type {before.get('fix_type')}")

    # Main dispatcher
    def apply_fix(self, fix_type: str, args: Dict[str, Any]) -> Dict[str, Any]:
        # Defense-in-depth for Invariant I3: the MCP layer already refuses FLAG
        # tier, but refuse here too so no caller can bypass the gate. No override.
        if args.get("tier") == "FLAG":
            raise ValueError("Cannot auto-fix a FLAG-tier issue (WPFixer gate).")
        if fix_type == "meta":
            return self.apply_meta_fix(
                args["post_id"], args["field"], args["new_value"]
            )
        elif fix_type == "redirect":
            return self.create_redirect(args["source_url"], args["target_url"])
        else:
            raise ValueError(f"Unknown fix type {fix_type}")

    def revert_fix(self, fix_type: str, token: Dict[str, Any]) -> bool:
        if fix_type == "meta":
            return self.revert_meta_fix(token)
        elif fix_type == "redirect":
            return self.revert_redirect(token)
        else:
            raise ValueError(f"Unknown fix type {fix_type}")
