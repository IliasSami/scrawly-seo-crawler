"""Branded, presentation-grade Technical SEO Audit report.

Produces a single self-contained HTML document (inline CSS + inline SVG charts,
no external assets) suitable for viewing, sharing, or printing to PDF. White-
label branding — agency name, accent colour, logo and contact line — is read
from global settings so agencies can hand the report to clients as their own.
"""
from __future__ import annotations

import html
import math
import os
from datetime import datetime
from typing import Any

from sentinelseo.db.models import URL, AppSettings, Client, Crawl, Fix, Issue
from sentinelseo.db.session import SessionLocal

_SEV_RANK = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2, "Info": 1}
_SEV_ORDER = ["Critical", "High", "Medium", "Low", "Info"]
_SEV_COLORS = {
    "Critical": "#dc2626", "High": "#d97706", "Medium": "#0ea5e9",
    "Low": "#6366f1", "Info": "#94a3b8",
}


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def _link(url: str) -> str:
    """A complete, clickable link — full URL (with domain) as both href and text."""
    if not url:
        return "—"
    safe = _esc(url)
    return f'<a href="{safe}" target="_blank" rel="noopener" title="{safe}">{safe}</a>'


def _status_class(code: int) -> str:
    if not code:
        return "st-err"
    if code >= 500:
        return "st-5xx"
    if code >= 400:
        return "st-4xx"
    if code >= 300:
        return "st-3xx"
    return "st-2xx"


def _grade(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Needs work"
    if score >= 25:
        return "Poor"
    return "Critical"


def _health_color(score: int) -> str:
    if score >= 75:
        return "#16a34a"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def _ring(score: int, color: str, size: int = 150, stroke: int = 14) -> str:
    r = (size - stroke) / 2
    circ = 2 * math.pi * r
    off = circ * (1 - max(0, min(100, score)) / 100)
    c = size / 2
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" class="ring">'
        f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="var(--line)" stroke-width="{stroke}"/>'
        f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{off:.1f}" '
        f'transform="rotate(-90 {c} {c})"/>'
        f'<text x="{c}" y="{c}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="{size * 0.30:.0f}" font-weight="800" fill="var(--ink)">{score}</text>'
        f"</svg>"
    )


def _donut(segments: list[tuple[str, int, str]], size: int = 150, stroke: int = 24) -> str:
    total = sum(v for _, v, _ in segments) or 1
    r = (size - stroke) / 2
    circ = 2 * math.pi * r
    c = size / 2
    parts: list[str] = []
    offset = 0.0
    for _label, val, color in segments:
        if val <= 0:
            continue
        dash = circ * (val / total)
        parts.append(
            f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-dasharray="{dash:.2f} {circ - dash:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {c} {c})"/>'
        )
        offset += dash
    center = (
        f'<text x="{c}" y="{c - 6}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="22" font-weight="800" fill="var(--ink)">{int(total)}</text>'
        f'<text x="{c}" y="{c + 14}" text-anchor="middle" font-size="10" '
        f'letter-spacing="0.08em" fill="var(--muted)">URLS</text>'
    )
    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{"".join(parts)}{center}</svg>'


def _hbars(items: list[tuple[str, int]], color: str) -> str:
    if not items:
        return '<p class="muted">No data.</p>'
    mx = max((v for _, v in items), default=1) or 1
    rows = []
    for label, val in items:
        pct = max(2.0, val / mx * 100)
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{_esc(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{pct:.1f}%;background:{color}"></span></span>'
            f'<span class="bar-val">{val}</span></div>'
        )
    return f'<div class="bars">{"".join(rows)}</div>'


def _sev_bar(sev: dict[str, int]) -> str:
    segs = []
    for k in _SEV_ORDER:
        v = sev.get(k, 0)
        if v <= 0:
            continue
        segs.append(
            f'<span class="sev-seg" style="flex-grow:{v};background:{_SEV_COLORS[k]}" title="{k}: {v}"></span>'
        )
    legend = "".join(
        f'<span class="lg"><span class="lg-dot" style="background:{_SEV_COLORS[k]}"></span>'
        f"{k} <b>{sev.get(k, 0)}</b></span>"
        for k in _SEV_ORDER
    )
    return (
        f'<div class="sev-track">{"".join(segs) or "<span class=sev-seg style=background:var(--line)></span>"}</div>'
        f'<div class="legend">{legend}</div>'
    )


class ReportGenerator:
    def __init__(self, template_dir: str | None = None) -> None:
        # Kept for API compatibility; the report is now rendered directly.
        self.template_dir = template_dir or os.path.join(os.path.dirname(__file__), "templates")

    # ------------------------------------------------------------------ data --
    def _branding(self, db: Any) -> dict[str, str]:
        row = db.query(AppSettings).filter(AppSettings.id == 1).first()
        data = dict(row.data) if row and row.data else {}
        return {
            "name": (data.get("report_brand_name") or "Scrawly").strip(),
            "color": (data.get("report_brand_color") or "#6366f1").strip(),
            "logo": (data.get("report_brand_logo") or "").strip(),
            "contact": (data.get("report_brand_contact") or "").strip(),
        }

    def generate_html(self, crawl_id: int) -> str:
        db = SessionLocal()
        try:
            crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
            if not crawl:
                raise ValueError(f"Crawl {crawl_id} not found.")
            issues = db.query(Issue).filter(Issue.crawl_id == crawl_id).all()
            urls = db.query(URL).filter(URL.crawl_id == crawl_id).all()
            client = db.query(Client).filter(Client.id == crawl.client_id).first()
            brand = self._branding(db)
        finally:
            db.close()

        from sentinelseo.checks import load_all_checks
        load_all_checks()
        from sentinelseo.checks.registry import get_all_checks
        from sentinelseo.checks.site_level.registry import get_site_level_checks
        all_checks = get_all_checks()
        site_checks = get_site_level_checks()

        # ---- aggregations (mirror the dashboard) --------------------------
        total = len(urls)
        indexable = sum(1 for u in urls if u.indexable)
        status_classes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}
        broken = 0
        depth_counts: dict[int, int] = {}
        segment_counts: dict[str, int] = {}
        for u in urls:
            st = u.status or 0
            if 200 <= st < 300:
                status_classes["2xx"] += 1
            elif 300 <= st < 400:
                status_classes["3xx"] += 1
            elif 400 <= st < 500:
                status_classes["4xx"] += 1
                broken += 1
            elif st >= 500:
                status_classes["5xx"] += 1
                broken += 1
            else:
                status_classes["other"] += 1
            if u.depth is not None:
                depth_counts[u.depth] = depth_counts.get(u.depth, 0) + 1
            seg = getattr(u, "segment", None)
            if seg:
                segment_counts[seg] = segment_counts.get(seg, 0) + 1

        # Group issues one-per-check, decorate with spec metadata + domain.
        grouped_by_check: dict[str, Issue] = {}
        for issue in issues:
            if issue.check_id not in grouped_by_check:
                issue.affected_url_ids = list(issue.affected_url_ids or [])
                grouped_by_check[issue.check_id] = issue
            elif issue.affected_url_ids:
                ex = grouped_by_check[issue.check_id]
                ex.affected_url_ids = list(set(list(ex.affected_url_ids or []) + list(issue.affected_url_ids)))

        severity: dict[str, int] = dict.fromkeys(_SEV_ORDER, 0)
        by_domain: dict[str, list[Issue]] = {}
        for issue in grouped_by_check.values():
            spec = None
            if issue.check_id in all_checks:
                spec = all_checks[issue.check_id][0]
            elif issue.check_id in site_checks:
                spec = site_checks[issue.check_id][0]
            domain = spec.domain if spec else "Other"
            issue.check_title = spec.title if spec else issue.check_id
            issue.why_it_matters = issue.why_it_matters or (spec.why_it_matters if spec else "")
            if issue.severity in severity:
                severity[issue.severity] += 1
            by_domain.setdefault(domain, []).append(issue)

        for dom in by_domain:
            by_domain[dom].sort(key=lambda i: _SEV_RANK.get(i.severity, 0), reverse=True)
        domains = sorted(
            by_domain,
            key=lambda d: max(_SEV_RANK.get(i.severity, 0) for i in by_domain[d]),
            reverse=True,
        )

        issue_total = len(grouped_by_check)
        from sentinelseo.audit.health import compute_health
        health = compute_health(total, indexable, broken, grouped_by_check.values())

        # Top priority issues across all domains (Critical/High first).
        priority = sorted(
            grouped_by_check.values(),
            key=lambda i: (_SEV_RANK.get(i.severity, 0), len(i.affected_url_ids or [])),
            reverse=True,
        )
        priority = [i for i in priority if _SEV_RANK.get(i.severity, 0) >= 3][:8]

        site = (client.base_url if client else "") or (crawl.target_url or "")
        client_name = client.name if client else (crawl.target_url or "Audited site")
        generated = datetime.now().strftime("%B %d, %Y · %H:%M")

        # Fixes the agent has applied — for the "Fixed by agent" section.
        def _spec_title(cid: str) -> str:
            if cid in all_checks:
                return all_checks[cid][0].title
            if cid in site_checks:
                return site_checks[cid][0].title
            return cid

        fix_rows = (
            db.query(Fix).filter(Fix.issue_id.in_([i.id for i in issues])).order_by(Fix.id.desc()).all()
            if issues else []
        )
        fixes_out = []
        for f in fix_rows:
            if f.reverted:
                continue
            after = f.after_state or {}
            fixes_out.append({
                "title": _spec_title(f.check_id),
                "field": after.get("field") or "",
                "value": after.get("new_value") or "",
                "url": after.get("url") or "",
            })

        # ---- render -------------------------------------------------------
        url_by_id = {u.id: u for u in urls}
        urls_sorted = sorted(urls, key=lambda u: (u.depth if u.depth is not None else 99, u.address))
        return self._render(
            brand=brand, client_name=client_name, site=site, crawl_id=crawl_id,
            generated=generated, health=health, total=total, indexable=indexable,
            broken=broken, issue_total=issue_total, severity=severity,
            status_classes=status_classes, segment_counts=segment_counts,
            depth_counts=depth_counts, priority=priority, by_domain=by_domain,
            domains=domains, url_by_id=url_by_id, urls=urls_sorted, fixes=fixes_out,
            agentic=(crawl.agentic_report if crawl else None) or {},
        )

    # --------------------------------------------------------------- render --
    def _render(self, **d: Any) -> str:
        brand = d["brand"]
        accent = brand["color"]
        health = d["health"]
        sev = d["severity"]
        sc = d["status_classes"]

        logo = (
            f'<img src="{_esc(brand["logo"])}" alt="{_esc(brand["name"])}" class="brand-logo">'
            if brand["logo"]
            else f'<div class="brand-mark">{_esc(brand["name"][:1] or "S")}</div>'
        )

        # Stat cards
        idx_pct = round(d["indexable"] / d["total"] * 100) if d["total"] else 0
        stat_cards = "".join(
            f'<div class="stat"><div class="stat-v" style="{style}">{val}</div><div class="stat-l">{label}</div></div>'
            for val, label, style in [
                (d["total"], "Pages crawled", ""),
                (f"{idx_pct}%", "Indexable", ""),
                (d["broken"], "Broken (4xx/5xx)", f"color:{'#dc2626' if d['broken'] else 'inherit'}"),
                (d["issue_total"], "Total issues", ""),
                (sev["Critical"], "Critical", f"color:{'#dc2626' if sev['Critical'] else 'inherit'}"),
                (sev["High"], "High", f"color:{'#d97706' if sev['High'] else 'inherit'}"),
            ]
        )

        status_donut = _donut([
            ("2xx", sc["2xx"], "#16a34a"), ("3xx", sc["3xx"], "#0ea5e9"),
            ("4xx", sc["4xx"], "#d97706"), ("5xx", sc["5xx"], "#dc2626"),
            ("other", sc["other"], "#94a3b8"),
        ])
        status_legend = "".join(
            f'<span class="lg"><span class="lg-dot" style="background:{col}"></span>{lbl} <b>{sc[lbl]}</b></span>'
            for lbl, col in [("2xx", "#16a34a"), ("3xx", "#0ea5e9"), ("4xx", "#d97706"), ("5xx", "#dc2626")]
            if sc[lbl]
        )

        cats = sorted(((dom, len(d["by_domain"][dom])) for dom in d["by_domain"]), key=lambda x: x[1], reverse=True)
        cat_bars = _hbars(cats[:8], accent)
        segs = sorted(d["segment_counts"].items(), key=lambda x: x[1], reverse=True)
        seg_bars = _hbars(segs[:8], "#a855f7") if segs else '<p class="muted">No segments defined.</p>'
        depth_items = [(f"Depth {k}", d["depth_counts"][k]) for k in sorted(d["depth_counts"])]
        depth_bars = _hbars(depth_items, "#0ea5e9")

        # Priority issues
        def issue_card(i: Any) -> str:
            n = len(i.affected_url_ids or [])
            fix = getattr(i, "recommended_fix", "") or ""
            return (
                f'<div class="issue">'
                f'<div class="issue-top"><span class="sev sev-{i.severity.lower()}">{_esc(i.severity)}</span>'
                f'<span class="issue-title">{_esc(getattr(i, "check_title", i.check_id))}</span>'
                f'<span class="issue-count">{n} page{"s" if n != 1 else ""}</span></div>'
                f'<div class="issue-why">{_esc(i.why_it_matters or "")}</div>'
                + (f'<div class="issue-fix"><b>Fix:</b> {_esc(fix)}</div>' if fix else "")
                + "</div>"
            )

        priority_html = (
            "".join(issue_card(i) for i in d["priority"])
            if d["priority"]
            else '<p class="muted">No high-priority issues — nicely done.</p>'
        )

        # Fixes applied by the agent (task-56 surface). Grouped by finding.
        fixes = d.get("fixes") or []
        fixes_html = ""
        if fixes:
            frows = "".join(
                f'<tr><td class="fx-t">{_esc(f["title"])}</td>'
                f'<td class="fx-f">{_esc(f["field"])}</td>'
                f'<td class="fx-u">{_link(f["url"])}</td>'
                f'<td class="fx-v">{_esc(f["value"])}</td></tr>'
                for f in fixes
            )
            fixes_html = (
                f'<p class="fx-lead">The {_esc(brand["name"])} agent autonomously applied '
                f'<b>{len(fixes)}</b> fix{"es" if len(fixes) != 1 else ""} to this site — each written to '
                f'WordPress with a rollback snapshot.</p>'
                '<table class="fx-table"><thead><tr><th>Issue</th><th>Field</th><th>Page</th>'
                '<th>New value</th></tr></thead>'
                f'<tbody>{frows}</tbody></table>'
            )

        # Full findings by domain — collapsible sections; each finding lists EVERY
        # affected page as a complete, clickable link.
        url_by_id = d["url_by_id"]

        def _affected(issue: Any) -> list[str]:
            out = []
            for uid in (issue.affected_url_ids or []):
                u = url_by_id.get(uid)
                if u is not None:
                    out.append(u.address)
            return out

        domain_sections = []
        for dom in d["domains"]:
            items = []
            for i in d["by_domain"][dom]:
                urls = _affected(i)
                n = len(urls)
                fix = getattr(i, "recommended_fix", "") or ""
                links = "".join(f"<li>{_link(u)}</li>" for u in urls)
                urls_html = f'<ul class="fd-urls">{links}</ul>' if urls else ""
                items.append(
                    f'<div class="fd-item">'
                    f'<div class="fd-item-head"><span class="sev sev-{i.severity.lower()}">{_esc(i.severity)}</span>'
                    f'<span class="fd-item-title">{_esc(getattr(i, "check_title", i.check_id))}</span>'
                    f'<span class="fd-item-n">{n} page{"s" if n != 1 else ""}</span></div>'
                    + (f'<div class="fd-item-why">{_esc(i.why_it_matters or "")}</div>' if i.why_it_matters else "")
                    + (f'<div class="fd-item-fix"><b>Fix:</b> {_esc(fix)}</div>' if fix else "")
                    + urls_html + "</div>"
                )
            domain_sections.append(
                f'<details class="fd-block" open><summary class="fd-sum">{_esc(dom)} '
                f'<span class="fd-count">{len(d["by_domain"][dom])}</span></summary>'
                + "".join(items) + "</details>"
            )
        findings_html = "".join(domain_sections) or '<p class="muted">No findings recorded.</p>'

        # Complete page inventory — every crawled URL, clickable, with key metrics.
        inv_rows = []
        for u in d["urls"]:
            st = u.status or 0
            idx = "Yes" if u.indexable else "No"
            inv_rows.append(
                f'<tr><td class="inv-url">{_link(u.address)}</td>'
                f'<td><span class="stc {_status_class(st)}">{st or "—"}</span></td>'
                f'<td class="inv-idx{"" if u.indexable else " inv-no"}">{idx}</td>'
                f'<td class="inv-num">{u.depth if u.depth is not None else "—"}</td>'
                f'<td class="inv-num">{u.word_count or 0}</td>'
                f'<td class="inv-t">{_esc((u.title or "")[:90])}</td></tr>'
            )
        inventory_html = (
            '<table class="inv-table"><thead><tr><th>URL</th><th>Status</th><th>Index</th>'
            '<th>Depth</th><th>Words</th><th>Title</th></tr></thead>'
            f'<tbody>{"".join(inv_rows)}</tbody></table>'
            if inv_rows else '<p class="muted">No pages crawled.</p>'
        )

        contact = (
            f'<div class="foot-contact">{_esc(brand["contact"])}</div>' if brand["contact"] else ""
        )

        fixes_section = (
            f'<div class="section" id="sec-fixed"><div class="section-title">'
            f'Fixed by the {_esc(brand["name"])} agent</div>{fixes_html}</div>'
            if fixes_html else ""
        )

        # --- Agentic Web readiness -----------------------------------------
        # Origin-level, so it renders as a scored checklist rather than a table
        # of affected URLs. Only actionable rows are listed: a report that
        # repeats 22 passing checks buries the handful that need work.
        ag = d.get("agentic") or {}
        agentic_section = ""
        if ag.get("results"):
            cat_rows = "".join(
                f'<tr><td>{_esc(c["label"])}</td>'
                f'<td class="num">{"—" if c["score"] is None else str(c["score"]) + "%"}</td>'
                f'<td class="num">{c["passed"]}/{c["total"]}</td></tr>'
                for c in ag.get("categories", [])
            )
            todo = [r for r in ag["results"] if r["status"] in ("fail", "info")]
            todo_rows = "".join(
                f'<details class="fd-block"><summary class="fd-sum">'
                f'<span class="sev sev-{"high" if r["status"] == "fail" else "low"}">'
                f'{"Fail" if r["status"] == "fail" else "Info"}</span> '
                f'{_esc(r["title"])} — {_esc(r["conclusion"])}</summary>'
                f'<div class="fd-body"><p><b>Goal.</b> {_esc(r["goal"])}</p>'
                + (f'<p><b>How to fix.</b> {_esc(r["remediation"])}</p>'
                   if r.get("remediation") else "")
                + (f'<pre class="ag-prompt">{_esc(r["fix_prompt"])}</pre>'
                   if r.get("fix_prompt") else "")
                + "</div></details>"
                for r in todo
            )
            passed = [r for r in ag["results"] if r["status"] == "pass"]
            passed_html = (
                '<p class="muted">Passing: '
                + ", ".join(_esc(r["title"]) for r in passed) + "</p>"
                if passed else ""
            )
            agentic_section = (
                '<div class="section" id="sec-agentic">'
                '<div class="section-title">Agentic Web readiness</div>'
                f'<p class="muted">Whether an AI agent can discover, read, '
                f'authenticate against and transact with this site. Score '
                f'<b>{ag.get("score", 0)}/100</b> — {_esc(ag.get("level", ""))}: '
                f'{_esc(ag.get("level_label", ""))} '
                f'({ag.get("passed", 0)}/{ag.get("scored", 0)} checks passed).</p>'
                f'<table class="tbl"><thead><tr><th>Category</th><th class="num">Score</th>'
                f'<th class="num">Passed</th></tr></thead><tbody>{cat_rows}</tbody></table>'
                f'{passed_html}'
                + (f'<div class="section-sub">Needs action ({len(todo)})</div>{todo_rows}'
                   if todo_rows else "")
                + "</div>"
            )

        toc_items = [("sec-exec", "Summary"), ("sec-viz", "Overview"),
                     ("sec-priority", "Priorities"), ("sec-findings", "All findings"),
                     ("sec-inventory", "Page inventory")]
        if agentic_section:
            toc_items.insert(1, ("sec-agentic", "Agentic readiness"))
        if fixes_html:
            toc_items.insert(1, ("sec-fixed", "Fixed by agent"))
        toc_html = '<div class="toc">' + "".join(
            f'<a href="#{i}">{_esc(lbl)}</a>' for i, lbl in toc_items
        ) + "</div>"

        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(brand['name'])} — Technical SEO Audit · {_esc(d['client_name'])}</title>
<style>
:root {{ --accent:{accent}; --ink:#0f172a; --muted:#64748b; --line:#e6e8ec;
  --bg:#f6f7f9; --surface:#ffffff; --radius:12px; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  font-size:14px; line-height:1.55; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.wrap {{ max-width:960px; margin:0 auto; padding:32px 24px 64px; }}
h1,h2,h3 {{ margin:0; letter-spacing:-0.01em; }}
.muted {{ color:var(--muted); }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:24px; }}

/* Cover */
.cover {{ background:linear-gradient(135deg, var(--accent), color-mix(in srgb, var(--accent) 55%, #a855f7));
  color:#fff; border-radius:var(--radius); padding:40px; display:flex; justify-content:space-between; align-items:center; gap:24px; }}
.cover-l {{ min-width:0; }}
.cover-brand {{ display:flex; align-items:center; gap:12px; margin-bottom:24px; }}
.brand-logo {{ height:36px; width:auto; background:#fff; border-radius:8px; padding:4px; }}
.brand-mark {{ height:36px; width:36px; border-radius:9px; background:rgba(255,255,255,.22);
  display:grid; place-items:center; font-weight:800; font-size:20px; }}
.brand-name {{ font-weight:700; font-size:16px; }}
.cover h1 {{ font-size:30px; font-weight:800; margin-bottom:8px; }}
.cover-site {{ font-size:15px; opacity:.92; word-break:break-all; }}
.cover-meta {{ margin-top:16px; font-size:13px; opacity:.85; }}
.cover-ring {{ background:rgba(255,255,255,.15); border-radius:16px; padding:18px 22px; text-align:center; flex:none; }}
.cover-ring .ring circle:first-child {{ stroke:rgba(255,255,255,.25); }}
.cover-ring .ring text {{ fill:#fff; }}
.cover-grade {{ margin-top:6px; font-weight:700; font-size:14px; }}
.cover-grade small {{ display:block; font-weight:500; opacity:.8; font-size:11px; letter-spacing:.08em; text-transform:uppercase; }}

.section {{ margin-top:28px; }}
.section-title {{ font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.09em; color:var(--muted); margin-bottom:12px; }}

.stats {{ display:grid; grid-template-columns:repeat(6,1fr); gap:12px; }}
.stat {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:14px; }}
.stat-v {{ font-size:26px; font-weight:800; line-height:1.1; }}
.stat-l {{ font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); margin-top:2px; }}

.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.viz-h {{ font-size:14px; font-weight:700; margin-bottom:14px; }}
.viz-flex {{ display:flex; align-items:center; gap:20px; }}
.ring text {{ font-family:inherit; }}
.legend {{ display:flex; flex-wrap:wrap; gap:8px 14px; margin-top:12px; }}
.lg {{ font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }}
.lg b {{ color:var(--ink); }}
.lg-dot {{ width:9px; height:9px; border-radius:50%; display:inline-block; }}

.sev-track {{ display:flex; height:14px; border-radius:999px; overflow:hidden; background:var(--line); }}
.sev-seg {{ min-width:3px; }}

.bars {{ display:flex; flex-direction:column; gap:9px; }}
.bar-row {{ display:grid; grid-template-columns:120px 1fr 34px; align-items:center; gap:10px; font-size:12px; }}
.bar-label {{ color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.bar-track {{ background:var(--bg); border-radius:6px; height:16px; overflow:hidden; }}
.bar-fill {{ display:block; height:100%; border-radius:6px; }}
.bar-val {{ text-align:right; font-weight:700; font-variant-numeric:tabular-nums; }}

.issue {{ border:1px solid var(--line); border-left:3px solid var(--accent); border-radius:8px; padding:12px 14px; margin-bottom:10px; background:var(--surface); }}
.issue-top {{ display:flex; align-items:center; gap:10px; }}
.issue-title {{ font-weight:700; flex:1; min-width:0; }}
.issue-count {{ font-size:11px; color:var(--muted); white-space:nowrap; }}
.issue-why {{ font-size:13px; color:var(--muted); margin-top:5px; }}
.issue-fix {{ font-size:13px; margin-top:6px; padding:7px 10px; background:var(--bg); border-radius:6px; }}
.sev {{ font-size:10px; font-weight:800; padding:2px 8px; border-radius:999px; text-transform:uppercase; letter-spacing:.03em; color:#fff; }}
.sev-critical {{ background:#dc2626; }} .sev-high {{ background:#d97706; }}
.sev-medium {{ background:#0ea5e9; }} .sev-low {{ background:#6366f1; }} .sev-info {{ background:#94a3b8; }}

/* Table of contents */
.toc {{ display:flex; flex-wrap:wrap; gap:8px; margin:4px 0 8px; }}
.toc a {{ font-size:12px; color:var(--muted); text-decoration:none; padding:4px 11px; border:1px solid var(--line); border-radius:999px; }}
.toc a:hover {{ color:var(--accent); border-color:var(--accent); }}

/* Fixed-by-agent section */
.fx-lead {{ color:var(--muted); margin-bottom:12px; }}
.fx-lead b {{ color:var(--ink); }}
.fx-table {{ width:100%; border-collapse:collapse; background:var(--surface); border:1px solid var(--line); border-radius:10px; overflow:hidden; font-size:12.5px; }}
.fx-table th {{ text-align:left; font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); padding:8px 12px; border-bottom:1px solid var(--line); background:var(--bg); }}
.fx-table td {{ padding:8px 12px; border-bottom:1px solid var(--line); vertical-align:top; }}
.fx-table tr:last-child td {{ border-bottom:none; }}
.fx-f {{ font-size:10px; text-transform:uppercase; font-weight:700; color:#16a34a; white-space:nowrap; }}
.fx-u a {{ color:var(--accent); text-decoration:none; word-break:break-all; }}
.fx-v {{ color:var(--ink); }}

/* Collapsible domain sections */
.fd-block {{ margin-bottom:12px; border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
.fd-sum {{ cursor:pointer; padding:11px 14px; font-size:15px; font-weight:700; background:var(--bg); display:flex; align-items:center; gap:8px; list-style:none; }}
.fd-sum::-webkit-details-marker {{ display:none; }}
.fd-sum::before {{ content:"▸"; color:var(--muted); font-size:12px; transition:transform .15s; }}
details[open] > .fd-sum::before {{ transform:rotate(90deg); }}
.fd-count {{ font-size:12px; color:var(--muted); background:var(--surface); border:1px solid var(--line); border-radius:999px; padding:1px 9px; font-weight:700; }}
/* Finding items (severity + title + why + fix + affected pages) */
.fd-item {{ padding:12px 14px; border-top:1px solid var(--line); }}
.fd-item-head {{ display:flex; align-items:center; gap:10px; }}
.fd-item-title {{ font-weight:700; flex:1; min-width:0; }}
.fd-item-n {{ font-size:11px; color:var(--muted); white-space:nowrap; }}
.fd-item-why {{ font-size:12.5px; color:var(--muted); margin-top:5px; }}
.fd-item-fix {{ font-size:12.5px; margin-top:6px; padding:7px 10px; background:var(--bg); border-radius:6px; }}
.fd-urls {{ list-style:none; margin:8px 0 0; padding:8px 10px; display:flex; flex-direction:column; gap:2px; background:var(--bg); border-radius:6px; max-height:230px; overflow:auto; }}
.fd-urls li {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:11.5px; }}
.fd-urls a {{ color:var(--accent); text-decoration:none; word-break:break-all; }}
.fd-urls a:hover {{ text-decoration:underline; }}

/* Page inventory — every crawled URL, clickable */
.inv-wrap {{ border:1px solid var(--line); border-radius:10px; overflow-x:auto; }}
.inv-table {{ width:100%; border-collapse:collapse; font-size:12px; }}
.inv-table th {{ position:sticky; top:0; text-align:left; font-size:10px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--line); background:var(--bg); }}
.inv-table td {{ padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:middle; }}
.inv-table tr:last-child td {{ border-bottom:none; }}
.inv-url {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
.inv-url a {{ color:var(--accent); text-decoration:none; word-break:break-all; }}
.inv-url a:hover {{ text-decoration:underline; }}
.inv-num {{ text-align:right; font-variant-numeric:tabular-nums; color:var(--muted); }}
.inv-idx {{ font-weight:600; color:#16a34a; }}
.inv-idx.inv-no {{ color:#d97706; }}
.inv-t {{ color:var(--muted); max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.stc {{ display:inline-block; min-width:34px; text-align:center; padding:1px 6px; border-radius:5px; font-size:11px; font-weight:800; font-variant-numeric:tabular-nums; }}
.st-2xx {{ color:#16a34a; background:rgba(22,163,74,.12); }}
.st-3xx {{ color:#2563eb; background:rgba(37,99,235,.12); }}
.st-4xx {{ color:#d97706; background:rgba(217,119,6,.14); }}
.st-5xx {{ color:#dc2626; background:rgba(220,38,38,.14); }}
.st-err {{ color:#dc2626; background:rgba(220,38,38,.14); }}

.foot {{ margin-top:36px; padding-top:18px; border-top:1px solid var(--line); display:flex; justify-content:space-between; align-items:center; color:var(--muted); font-size:12px; flex-wrap:wrap; gap:8px; }}
.foot-brand b {{ color:var(--ink); }}

@media print {{
  body {{ background:#fff; }}
  .wrap {{ max-width:none; padding:0; }}
  .section {{ break-inside:avoid; }}
  .issue, .fd-item {{ break-inside:avoid; }}
  .inv-table tr {{ break-inside:avoid; }}
  .cover {{ break-after:page; }}
  .section-inventory {{ break-before:page; }}
}}
@media (max-width:720px) {{
  .stats {{ grid-template-columns:repeat(3,1fr); }}
  .grid2 {{ grid-template-columns:1fr; }}
  .cover {{ flex-direction:column; align-items:flex-start; }}
}}
</style></head>
<body><div class="wrap">

  <div class="cover">
    <div class="cover-l">
      <div class="cover-brand">{logo}<span class="brand-name">{_esc(brand['name'])}</span></div>
      <h1>Technical SEO Audit</h1>
      <div class="cover-site">{_esc(d['site'])}</div>
      <div class="cover-meta">{_esc(d['client_name'])} · Crawl #{d['crawl_id']} · {_esc(d['generated'])}</div>
    </div>
    <div class="cover-ring">
      <div class="ring">{_ring(health, '#ffffff')}</div>
      <div class="cover-grade">{_grade(health)}<small>Health score</small></div>
    </div>
  </div>

  {toc_html}

  <div class="section" id="sec-exec">
    <div class="section-title">Executive summary</div>
    <div class="stats">{stat_cards}</div>
  </div>

  {fixes_section}

  {agentic_section}

  <div class="section" id="sec-viz">
    <div class="section-title">Severity distribution</div>
    <div class="card">{_sev_bar(sev)}</div>
  </div>

  <div class="section">
    <div class="grid2">
      <div class="card"><div class="viz-h">Response codes</div>
        <div class="viz-flex">{status_donut}<div class="legend" style="flex-direction:column;gap:8px">{status_legend or '<span class=muted>No data</span>'}</div></div>
      </div>
      <div class="card"><div class="viz-h">Crawl depth</div>{depth_bars}</div>
    </div>
  </div>

  <div class="section">
    <div class="grid2">
      <div class="card"><div class="viz-h">Findings by category</div>{cat_bars}</div>
      <div class="card"><div class="viz-h">Content segments</div>{seg_bars}</div>
    </div>
  </div>

  <div class="section" id="sec-priority">
    <div class="section-title">Priority recommendations</div>
    {priority_html}
  </div>

  <div class="section" id="sec-findings">
    <div class="section-title">All findings</div>
    {findings_html}
  </div>

  <div class="section section-inventory" id="sec-inventory">
    <div class="section-title">Page inventory · {d['total']} crawled URL{'s' if d['total'] != 1 else ''}</div>
    <div class="inv-wrap">{inventory_html}</div>
  </div>

  <div class="foot">
    <div class="foot-brand">Report by <b>{_esc(brand['name'])}</b>{'' if brand['name'] == 'Scrawly' else ' · powered by Scrawly'}</div>
    {contact}
  </div>

</div></body></html>"""

    def generate_pdf(self, crawl_id: int, output_path: str) -> None:
        from pathlib import Path

        from sentinelseo.report.pdf import html_to_pdf_sync

        Path(output_path).write_bytes(html_to_pdf_sync(self.generate_html(crawl_id)))
