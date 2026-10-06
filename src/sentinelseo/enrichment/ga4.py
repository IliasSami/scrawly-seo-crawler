"""Google Analytics 4 enrichment (SF Pattern M).

Pulls per-page engagement from the GA4 Data API and matches it onto crawled URLs.
Auth comes from the shared OAuth grant (google_oauth) — the same consent that
covers Search Console — so a user connects once and gets both.

URL matching mirrors SF: GA4 reports a *page path*, the crawl has absolute URLs,
and the two disagree constantly over trailing slashes and case. We try the exact
path first, then optional fuzzy variants, preferring the highest-sessions row.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

# Metrics worth having by default; GA4 exposes ~65.
DEFAULT_METRICS = ["sessions", "engagedSessions", "screenPageViews", "conversions"]


class GA4Enricher:
    """Fetch GA4 page metrics for a property and key them by crawlable URL."""

    def __init__(self, property_id: str, metrics: Optional[List[str]] = None) -> None:
        self.property_id = str(property_id or "").strip().replace("properties/", "")
        self.metrics = metrics or DEFAULT_METRICS
        self.service: Any = None
        if not self.property_id:
            return
        try:
            from googleapiclient.discovery import build  # type: ignore[import-untyped]

            from sentinelseo.enrichment.google_oauth import load_credentials

            creds = load_credentials()
            if creds:
                self.service = build(
                    "analyticsdata", "v1beta", credentials=creds, cache_discovery=False
                )
        except Exception:  # noqa: BLE001 - enrichment is optional, never fatal
            self.service = None

    def fetch_page_metrics(self, days: int = 28, limit: int = 100_000) -> Dict[str, Any]:
        """{page_path: {metric: value}} for the last `days`. Empty when unavailable."""
        if not self.service or not self.property_id:
            return {}
        start = (date.today() - timedelta(days=days)).isoformat()
        end = date.today().isoformat()
        body = {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "pagePath"}],
            "metrics": [{"name": m} for m in self.metrics],
            "limit": limit,
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        }
        try:
            resp = (
                self.service.properties()
                .runReport(property=f"properties/{self.property_id}", body=body)
                .execute()
            )
        except Exception as e:  # noqa: BLE001
            return {"_error": str(e)[:200]}

        headers = [m["name"] for m in resp.get("metricHeaders", [])]
        out: Dict[str, Any] = {}
        for row in resp.get("rows", []):
            path = (row.get("dimensionValues") or [{}])[0].get("value", "")
            vals = row.get("metricValues", [])
            rec: Dict[str, Any] = {}
            for i, name in enumerate(headers):
                raw = vals[i].get("value") if i < len(vals) else "0"
                try:
                    rec[name] = float(raw) if "." in str(raw) else int(raw)
                except (TypeError, ValueError):
                    rec[name] = 0
            # Keep the highest-sessions row when GA4 reports a path more than once.
            if path not in out or rec.get("sessions", 0) > out[path].get("sessions", 0):
                out[path] = rec
        return out


def _variants(path: str, fuzzy: bool) -> List[str]:
    """Path forms to try, in preference order (SF's trailing-slash matching)."""
    out = [path]
    if not fuzzy:
        return out
    out.append(path.rstrip("/") if path.endswith("/") and path != "/" else path + "/")
    # An index document and its directory are the same page to a user.
    for idx in ("/index.html", "/index.htm", "/index.php"):
        if path.endswith(idx):
            out.append(path[: -len(idx)] + "/")
    return list(dict.fromkeys(out))


def match_to_urls(
    metrics_by_path: Dict[str, Any], addresses: List[str], fuzzy: bool = True
) -> Dict[str, Any]:
    """Key GA4 page-path metrics by crawled absolute URL (SF Pattern M).

    Case matching is symmetric: GA4 preserves original capitalization, the crawl
    may lowercase URLs, and either side can differ — so when fuzzy, we look up
    against a lowercased index of the GA4 keys, not just a lowercased crawl path.
    """
    if not metrics_by_path or "_error" in metrics_by_path:
        return {}
    lower_index = {k.lower(): v for k, v in metrics_by_path.items()} if fuzzy else {}
    out: Dict[str, Any] = {}
    for addr in addresses:
        try:
            path = urlsplit(addr).path or "/"
        except ValueError:
            continue
        for cand in _variants(path, fuzzy):
            if cand in metrics_by_path:
                out[addr] = metrics_by_path[cand]
                break
            if fuzzy and cand.lower() in lower_index:
                out[addr] = lower_index[cand.lower()]
                break
    return out
