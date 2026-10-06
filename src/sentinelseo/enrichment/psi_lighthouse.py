import os
from typing import Any, Dict, Optional

import requests


class PSILighthouseEnricher:
    """PageSpeed Insights enrichment (FR-E2).

    Returns lab Lighthouse metrics/scores plus CrUX **field** Core Web Vitals when
    the URL/origin has enough real-user data (low-traffic sites return no field
    data — that is expected, not an error). `PAGESPEED_API_KEY` env var required.
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("PAGESPEED_API_KEY")

    def fetch_metrics(self, url: str, strategy: str = "mobile") -> Dict[str, Any]:
        if not self.api_key:
            return {"available": False, "reason": "no PAGESPEED_API_KEY"}

        api_url = (
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
            f"?url={url}&key={self.api_key}&strategy={strategy}"
            "&category=performance&category=accessibility"
            "&category=best-practices&category=seo"
        )
        try:
            resp = requests.get(api_url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            return {"available": False, "reason": str(e)[:200]}

        lh = data.get("lighthouseResult", {})
        audits = lh.get("audits", {})
        cats = lh.get("categories", {})

        def _lab(name: str, div: float = 1.0) -> Optional[float]:
            v = audits.get(name, {}).get("numericValue")
            return round(v / div, 3) if v is not None else None

        def _field(metric: str) -> Optional[float]:
            m = data.get("loadingExperience", {}).get("metrics", {}).get(metric, {})
            p = m.get("percentile")
            return float(p) if p is not None else None

        def _score(cat: str) -> Optional[int]:
            s = cats.get(cat, {}).get("score")
            return int(s * 100) if s is not None else None

        field_lcp = _field("LARGEST_CONTENTFUL_PAINT_MS")
        field_inp = _field("INTERACTION_TO_NEXT_PAINT")
        field_cls = _field("CUMULATIVE_LAYOUT_SHIFT_SCORE")
        has_field = any(x is not None for x in (field_lcp, field_inp, field_cls))

        return {
            "available": True,
            "source": "field" if has_field else "lab",
            # Prefer CrUX field values; fall back to lab.
            "lcp_s": (field_lcp / 1000.0) if field_lcp is not None else _lab("largest-contentful-paint", 1000.0),  # noqa: E501
            "inp_ms": float(field_inp) if field_inp is not None else None,  # INP is field-only  # noqa: E501
            "cls": (field_cls / 100.0) if field_cls is not None else _lab("cumulative-layout-shift"),  # noqa: E501
            "scores": {
                "performance": _score("performance"),
                "accessibility": _score("accessibility"),
                "best_practices": _score("best-practices"),
                "seo": _score("seo"),
            },
        }
