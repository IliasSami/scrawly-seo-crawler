import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from sentinelseo.db.models import URL, Client, Crawl, Fix, Issue
from sentinelseo.db.session import SessionLocal
from sentinelseo.enrichment.psi_lighthouse import PSILighthouseEnricher
from sentinelseo.report.differ import diff_crawls as run_diff_crawls
from sentinelseo.report.generator import ReportGenerator
from sentinelseo.wp.client import WPClient
from sentinelseo.wp.fixes import WPFixer

mcp = FastMCP("Scrawly")


def _get_fixer() -> WPFixer:
    """Helper to instantiate the WordPress fixer using environment variables."""
    wp_url = os.environ.get("SCRAWLY_WP_URL", "http://localhost:8080")
    wp_user = os.environ.get("SCRAWLY_WP_USER")
    wp_pass = os.environ.get("SCRAWLY_WP_APP_PASS")

    if not wp_user or not wp_pass:
        raise ValueError(
            "WordPress credentials not configured. "
            "Set SCRAWLY_WP_USER and SCRAWLY_WP_APP_PASS."
        )

    client = WPClient(wp_url, wp_user, wp_pass)
    client.detect_seo_plugins()
    return WPFixer(client)


# STAGE 1: Read-only tools
# Crawls are started from the Scrawly app (it runs the full crawl, enrichment and
# audit pipeline); these tools read and act on the audits it produced.
@mcp.tool()
def list_crawls(limit: int = 20) -> List[Dict[str, Any]]:
    """Lists the most recent audits (newest first) with their crawl ids."""
    db = SessionLocal()
    try:
        crawls = db.query(Crawl).order_by(Crawl.id.desc()).limit(max(1, min(limit, 200))).all()
        names = {c.id: c.name for c in db.query(Client).all()}
        return [
            {"crawl_id": c.id, "site": names.get(c.client_id, ""), "target_url": c.target_url,
             "started_at": c.started_at.isoformat() if c.started_at else None,
             "pages": c.url_count}
            for c in crawls
        ]
    finally:
        db.close()


@mcp.tool()
def get_issues(
    crawl_id: int, severity: Optional[str] = None, tier: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves detected issues for a crawl, optionally filtered by severity."""
    db = SessionLocal()
    query = db.query(Issue).filter(Issue.crawl_id == crawl_id)
    if severity:
        query = query.filter(Issue.severity == severity)
    if tier:
        query = query.filter(Issue.tier == tier)

    issues = query.all()
    db.close()
    return [
        {"id": i.id, "check_id": i.check_id, "severity": i.severity, "tier": i.tier}
        for i in issues
    ]


@mcp.tool()
def get_page_detail(url_id: int) -> Dict[str, Any]:
    """Retrieves details of a specific crawled page."""
    db = SessionLocal()
    url = db.query(URL).filter(URL.id == url_id).first()
    db.close()
    if not url:
        return {"error": "URL not found"}
    return {
        "id": url.id,
        "address": url.address,
        "status": url.status,
        "title": url.title,
    }


@mcp.tool()
def run_lighthouse(url: str) -> Dict[str, Any]:
    """Runs Lighthouse / PageSpeed Insights against a URL."""
    enricher = PSILighthouseEnricher()
    return enricher.fetch_metrics(url)


@mcp.tool()
def check_ai_access(url: str) -> Dict[str, Any]:
    """Per-UA allow/block matrix for AI crawlers (robots.txt + live fetch)."""
    import asyncio

    import httpx

    from sentinelseo.crawl.fetcher import Crawler

    crawler = Crawler(render=False)

    async def _run() -> Dict[str, Any]:
        async with httpx.AsyncClient(follow_redirects=True, verify=False) as c:
            await crawler.probe_ai_access(c, url)
        return crawler.ai_access.matrix if crawler.ai_access else {}

    matrix = asyncio.run(_run())
    blocked = [
        b for b, v in matrix.items()
        if not v.get("robots_allowed") or not v.get("live_ok")
    ]
    return {"url": url, "matrix": matrix, "blocked_bots": blocked}


@mcp.tool()
def generate_report(crawl_id: int, format: str = "html") -> Dict[str, Any]:
    """Generates an audit report in HTML or PDF format."""
    generator = ReportGenerator()
    if format.lower() == "pdf":
        output_path = str(Path(tempfile.gettempdir()) / f"scrawly_report_{crawl_id}.pdf")
        generator.generate_pdf(crawl_id, output_path)
        return {"status": "generated", "path": output_path, "format": "pdf"}
    else:
        html = generator.generate_html(crawl_id)
        # Returning truncated HTML or path in actual usage
        return {"status": "generated", "content_length": len(html), "format": "html"}


@mcp.tool()
def diff_crawls(crawl_id_a: int, crawl_id_b: int) -> Dict[str, Any]:
    """Diffs two crawls to identify resolved and new issues."""
    return run_diff_crawls(crawl_id_a, crawl_id_b)


# STAGE 2: Mutating tools
@mcp.tool()
def propose_fix(issue_id: int) -> Dict[str, Any]:
    """Describes the recommended fix for an issue and the pages it affects.
    Nothing is written; apply_fix (with confirm=True) performs the change."""
    db = SessionLocal()
    try:
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            raise ValueError("Issue not found")
        ids = list(issue.affected_url_ids or [])
        urls = [u.address for u in db.query(URL).filter(URL.id.in_(ids)).limit(50).all()] if ids else []
        return {
            "issue_id": issue_id,
            "check_id": issue.check_id,
            "severity": issue.severity,
            "tier": issue.tier,
            "auto_fixable": issue.tier != "FLAG",
            "why_it_matters": issue.why_it_matters,
            "recommended_fix": issue.recommended_fix,
            "affected_urls": urls,
        }
    finally:
        db.close()


@mcp.tool()
def apply_fix(
    issue_id: int,
    confirm: bool = False,
    fix_type: str = "meta",
    args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Applies a safe auto-fix to the live WordPress site.
    WARNING: confirm=True must be explicitly passed.
    """
    if not args:
        args = {}

    db = SessionLocal()
    issue = db.query(Issue).filter(Issue.id == issue_id).first()

    if not issue:
        db.close()
        raise ValueError("Issue not found")

    # INVARIANT: enforce FLAG tier gate. No override exists.
    if issue.tier == "FLAG":
        db.close()
        raise ValueError("Cannot auto-fix FLAG tier issue.")

    # Require explicit confirmation
    if not confirm:
        db.close()
        raise ValueError("confirm=True is required to apply fixes.")

    fixer = _get_fixer()
    args = {**args, "tier": issue.tier}  # let the fixer re-check the tier gate

    # I2 — capture before-state (read-only) and persist the rollback record to
    # the `fix` table BEFORE performing any write. If snapshotting fails, nothing
    # is written and no Fix row is created.
    try:
        before = fixer.snapshot(fix_type, args)
    except Exception:
        db.close()
        raise

    new_fix = Fix(
        issue_id=issue.id,
        check_id=issue.check_id,
        tier=issue.tier,
        before_state=before,
        after_state={},
        applied_by="mcp",
    )
    db.add(new_fix)
    db.commit()  # rollback record durable before the mutation
    db.refresh(new_fix)
    fix_id = new_fix.id

    # Perform the write. If it fails, the Fix row (with before-state) survives so
    # the change can still be reverted / inspected.
    try:
        token = fixer.commit_write(before)
    except Exception as e:
        issue.status = "failed"
        db.commit()
        db.close()
        raise Exception(
            f"Write failed; rollback record preserved (fix_id={fix_id})."
        ) from e

    new_fix.before_state = token  # finalized token carries action/ids for revert
    new_fix.after_state = args
    issue.status = "fixed"
    db.commit()
    db.close()

    return {"status": "success", "fix_id": fix_id, "rollback_token": token}


@mcp.tool()
def create_redirect(
    issue_id: int, source_url: str, target_url: str, confirm: bool = False
) -> Dict[str, Any]:
    """Creates a 301 redirect on the live WordPress site to resolve an issue.
    Goes through apply_fix, so the tier gate applies and a rollback record is
    stored before anything is written (revert with the returned fix_id)."""
    result: Dict[str, Any] = apply_fix(
        issue_id, confirm=confirm, fix_type="redirect",
        args={"source_url": source_url, "target_url": target_url})
    return result


@mcp.tool()
def revert(fix_id: int) -> Dict[str, Any]:
    """Reverts a previously applied fix using its stored before-state."""
    db = SessionLocal()
    fix_record = db.query(Fix).filter(Fix.id == fix_id).first()

    if not fix_record:
        db.close()
        raise ValueError("Fix record not found")

    if fix_record.reverted:
        db.close()
        return {"status": "already_reverted"}

    fixer = _get_fixer()

    # We infer fix type from args or check_id for MVP, assume meta for now
    fix_type = "meta"
    if "redirect_id" in fix_record.before_state:
        fix_type = "redirect"

    success = fixer.revert_fix(fix_type, fix_record.before_state)

    if success:
        fix_record.reverted = True

        # update issue status back to open
        issue = db.query(Issue).filter(Issue.id == fix_record.issue_id).first()
        if issue:
            issue.status = "open"

        db.commit()

    db.close()
    return {"status": "success", "reverted": success}


if __name__ == "__main__":
    mcp.run()
