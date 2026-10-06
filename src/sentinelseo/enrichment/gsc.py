import os
from datetime import date, timedelta
from typing import Any, Dict, List


class GSCEnricher:
    """Google Search Console enrichment (FR-E1).

    Authenticates with the service-account JSON at GOOGLE_APPLICATION_CREDENTIALS.
    The target property must exist in Search Console AND the service-account email
    must be granted access to it, otherwise queries return a permission error.
    """

    SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

    def __init__(self, property_url: str) -> None:
        self.property_url = property_url
        self.service: Any = None
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path and os.path.exists(creds_path):
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build  # type: ignore

                creds = service_account.Credentials.from_service_account_file(
                    creds_path, scopes=self.SCOPES
                )
                self.service = build(
                    "searchconsole", "v1", credentials=creds, cache_discovery=False
                )
            except Exception:
                self.service = None

    def list_properties(self) -> List[str]:
        if not self.service:
            return []
        try:
            sites = self.service.sites().list().execute()
            return [s["siteUrl"] for s in sites.get("siteEntry", [])]
        except Exception:
            return []

    def fetch_top_pages(self, days: int = 28) -> Dict[str, Any]:
        """Per-page impressions/clicks/ctr/position for the last `days`."""
        if not self.service:
            return {}
        end = date.today()
        start = end - timedelta(days=days)
        try:
            resp = (
                self.service.searchanalytics()
                .query(
                    siteUrl=self.property_url,
                    body={
                        "startDate": start.isoformat(),
                        "endDate": end.isoformat(),
                        "dimensions": ["page"],
                        "rowLimit": 1000,
                    },
                )
                .execute()
            )
            return {
                r["keys"][0]: {
                    "impressions": r.get("impressions", 0),
                    "clicks": r.get("clicks", 0),
                    "ctr": r.get("ctr", 0),
                    "position": r.get("position", 0),
                }
                for r in resp.get("rows", [])
            }
        except Exception as e:  # noqa: BLE001
            return {"_error": str(e)[:200]}
