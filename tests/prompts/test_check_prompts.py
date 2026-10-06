"""Every audit finding must yield a safe, stack-correct agent prompt.

Coverage here is a hard requirement, not a nice-to-have: a check with no prompt
is a finding the user cannot act on, and it would fail silently.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from sentinelseo.checks import load_all_checks
from sentinelseo.checks.registry import get_all_checks
from sentinelseo.prompts import (
    FAMILIES,
    build_check_prompt,
    family_for,
    kb,
    spec_for_check,
)
from sentinelseo.prompts.stacks import PROFILES


def _registry() -> Dict[str, Tuple[Any, Any]]:
    load_all_checks()
    return get_all_checks()


class TestTotalCoverage:
    def test_every_registered_check_produces_a_prompt(self) -> None:
        missing = []
        for cid, (spec, _) in _registry().items():
            p = build_check_prompt(
                cid, title=spec.title, domain=spec.domain,
                why_it_matters=spec.why_it_matters, severity=spec.default_severity,
                site_url="https://ex.com", stack="wordpress", use_kb=False)
            if p is None:
                missing.append(cid)
        assert not missing, f"checks with no prompt: {missing}"

    def test_no_prompt_is_a_stub(self) -> None:
        thin = []
        for cid, (spec, _) in _registry().items():
            p = build_check_prompt(
                cid, title=spec.title, domain=spec.domain,
                site_url="https://ex.com", stack="nextjs", use_kb=False)
            assert p is not None
            if len(p.text) < 400:
                thin.append((cid, len(p.text)))
        assert not thin, f"prompts too thin to act on: {thin}"

    def test_every_check_domain_has_a_family(self) -> None:
        """A new domain must not silently fall back to generic advice."""
        domains = {spec.domain for spec, _ in _registry().values()}
        unmapped = sorted(d for d in domains if d not in FAMILIES)
        assert not unmapped, f"domains without a prompt family: {unmapped}"

    def test_unknown_domain_still_yields_a_usable_prompt(self) -> None:
        p = build_check_prompt("Z99", title="Some new check",
                               domain="A Domain That Does Not Exist",
                               site_url="https://ex.com", stack="hugo", use_kb=False)
        assert p is not None and len(p.text) > 400

    def test_registry_fallback_when_no_metadata_supplied(self) -> None:
        """Passing only a check_id must still resolve via the live registry."""
        p = build_check_prompt("D01", site_url="https://ex.com", stack="wordpress",
                               use_kb=False)
        assert p is not None
        assert "title" in p.text.lower() or "Missing page title" in p.text

    def test_unknown_check_id_returns_none(self) -> None:
        assert build_check_prompt("NOPE99", site_url="https://ex.com",
                                  use_kb=False) is None


class TestPromptContent:
    def test_recommended_fix_leads_the_body(self) -> None:
        p = build_check_prompt(
            "B01", title="4xx errors", domain="Response codes & redirects",
            recommended_fix="Restore the page or 301 it.",
            site_url="https://ex.com", stack="nextjs", use_kb=False)
        assert p is not None
        assert "Restore the page or 301 it." in p.text

    def test_affected_urls_are_listed(self) -> None:
        p = build_check_prompt(
            "B01", title="4xx errors", domain="Response codes & redirects",
            site_url="https://ex.com", stack="nextjs",
            affected_urls=["https://ex.com/a", "https://ex.com/b"], use_kb=False)
        assert p is not None
        assert "https://ex.com/a" in p.text and "https://ex.com/b" in p.text

    def test_severity_is_surfaced(self) -> None:
        p = build_check_prompt("B01", title="4xx errors",
                               domain="Response codes & redirects",
                               severity="High", site_url="https://ex.com",
                               use_kb=False)
        assert p is not None and "[High]" in p.text


class TestArtefactScopedNotes:
    """Irrelevant platform notes are noise that make an agent second-guess."""

    def _notes(self, domain: str, stack: str) -> str:
        p = build_check_prompt("X", title="t", domain=domain,
                               site_url="https://ex.com", stack=stack, use_kb=False)
        assert p is not None
        return (p.text.split("### Platform notes")[1].split("\n##")[0]
                if "### Platform notes" in p.text else "")

    def test_redirect_fix_does_not_mention_robots_route_handler(self) -> None:
        notes = self._notes("Response codes & redirects", "nextjs")
        assert "app/robots.ts" not in notes

    def test_robots_fix_does_mention_the_route_handler_conflict(self) -> None:
        notes = self._notes("Crawlability & Indexability", "nextjs")
        assert "app/robots.ts" in notes

    def test_wordpress_core_warning_applies_everywhere(self) -> None:
        for domain in ("Response codes & redirects", "XML sitemaps",
                       "Titles, meta and headings"):
            assert "core files" in self._notes(domain, "wordpress"), domain


class TestSafetyAcrossEveryCheck:
    def test_no_generated_prompt_contains_a_destructive_command(self) -> None:
        banned = ("rm -rf", "DROP TABLE", "DROP DATABASE", "TRUNCATE TABLE",
                  "mkfs", "chmod 777", "git push --force", "> /dev/sd")
        reg = _registry()
        for cid, (spec, _) in reg.items():
            for stack in ("wordpress", "nextjs", "shopify", "generic"):
                p = build_check_prompt(cid, title=spec.title, domain=spec.domain,
                                       site_url="https://ex.com", stack=stack,
                                       use_kb=False)
                assert p is not None
                for bad in banned:
                    assert bad not in p.text, f"{cid}/{stack} contains {bad!r}"

    def test_every_prompt_carries_the_safety_constraints(self) -> None:
        for cid, (spec, _) in _registry().items():
            p = build_check_prompt(cid, title=spec.title, domain=spec.domain,
                                   site_url="https://ex.com", use_kb=False)
            assert p is not None
            assert "Never commit secrets" in p.text, cid

    def test_security_family_requires_csp_report_only_first(self) -> None:
        """A blindly-enforced CSP breaks sites; the prompt must say so."""
        p = build_check_prompt("SEC", title="Missing CSP", domain="Security",
                               site_url="https://ex.com", use_kb=False)
        assert p is not None and "report-only" in p.text.lower()

    def test_content_family_forbids_generating_filler(self) -> None:
        p = build_check_prompt("E02", title="Thin content",
                               domain="Content quality",
                               site_url="https://ex.com", use_kb=False)
        assert p is not None and "padding" in p.text.lower()

    def test_schema_family_forbids_marking_up_invisible_content(self) -> None:
        p = build_check_prompt("S", title="Missing schema",
                               domain="Structured data / schema",
                               site_url="https://ex.com", use_kb=False)
        assert p is not None and "not visible" in p.text.lower()


class TestKnowledgeBaseValidation:
    """The KB must never cache something unsafe or useless."""

    def test_rejects_too_short_guidance(self) -> None:
        assert kb.store("T01", "generic", "too short") is False

    def test_rejects_overlong_guidance(self) -> None:
        assert kb.store("T02", "generic", "x" * 5000) is False

    def test_rejects_destructive_commands(self) -> None:
        bad = ("To fix this on WordPress you should run rm -rf wp-content/ and "
               "then rebuild the site from scratch using the backup you took.")
        assert kb.store("T03", "generic", bad) is False

    def test_rejects_a_model_refusal(self) -> None:
        refusal = ("I cannot help with that request because it falls outside "
                   "what I am able to assist with in this particular context.")
        assert kb.store("T04", "generic", refusal) is False

    def test_accepts_and_returns_valid_guidance(self) -> None:
        good = ("On WordPress, register the header in a must-use plugin under "
                "wp-content/mu-plugins/ using the send_headers action so it "
                "survives theme and plugin updates.")
        assert kb.store("T05", "wordpress", good, source="manual") is True
        assert kb.lookup("T05", "wordpress") == good

    def test_manual_entries_win_over_generated_ones(self) -> None:
        ai = ("Generated guidance for this pair that is long enough to pass the "
              "minimum length validation check applied on write.")
        human = ("Hand-written guidance for this pair that is long enough to "
                 "pass the minimum length validation check applied on write.")
        kb.store("T06", "wordpress", ai, source="ai")
        kb.store("T06", "wordpress", human, source="manual")
        assert kb.lookup("T06", "wordpress") == human

    def test_lookup_miss_returns_none(self) -> None:
        assert kb.lookup("NEVER_STORED_XYZ", "generic") is None

    def test_enrich_without_ai_config_returns_none(self) -> None:
        """No API key must degrade to the template, never raise."""
        assert kb.enrich("T07", "generic", "Generic", "Some check", cfg=None) is None
        assert kb.enrich("T08", "generic", "Generic", "Some check", cfg={}) is None


class TestKnowledgeBaseLayering:
    def test_kb_guidance_is_layered_into_the_prompt(self) -> None:
        guidance = ("On Hugo, add the directive to layouts/robots.txt and set "
                    "enableRobotsTXT = true in hugo.toml so the template is used.")
        kb.store("T09", "hugo", guidance, source="manual")
        p = build_check_prompt("T09", title="Robots issue",
                               domain="Robots directives (file-level)",
                               site_url="https://ex.com", stack="hugo", use_kb=True)
        assert p is not None and guidance in p.text

    def test_use_kb_false_bypasses_the_cache(self) -> None:
        guidance = ("This guidance should not appear when the caller explicitly "
                    "opts out of the knowledge base layer for a render.")
        kb.store("T10", "hugo", guidance, source="manual")
        p = build_check_prompt("T10", title="Robots issue",
                               domain="Robots directives (file-level)",
                               site_url="https://ex.com", stack="hugo", use_kb=False)
        assert p is not None and guidance not in p.text

    def test_kb_entry_for_one_stack_does_not_leak_to_another(self) -> None:
        guidance = ("Hugo-specific guidance that must never be shown to someone "
                    "working on a completely different platform such as Shopify.")
        kb.store("T11", "hugo", guidance, source="manual")
        p = build_check_prompt("T11", title="Robots issue",
                               domain="Robots directives (file-level)",
                               site_url="https://ex.com", stack="shopify", use_kb=True)
        assert p is not None and guidance not in p.text


class TestFamilies:
    def test_every_family_has_acceptance_criteria(self) -> None:
        for domain, fam in FAMILIES.items():
            assert fam.acceptance, f"{domain} family has no acceptance criteria"
            assert len(fam.guidance) > 60, f"{domain} guidance is too thin"

    def test_family_artefacts_are_valid_locations(self) -> None:
        valid = {"robots", "sitemap", "headers", "static", "well_known"}
        for domain, fam in FAMILIES.items():
            assert fam.artefact in valid, f"{domain} -> unknown artefact {fam.artefact}"

    def test_unknown_domain_falls_back_to_the_default_family(self) -> None:
        fam = family_for("No Such Domain")
        assert fam.acceptance and fam.guidance

    def test_spec_for_check_is_pure(self) -> None:
        a = spec_for_check("X", "T", "Security")
        b = spec_for_check("X", "T", "Security")
        assert a.acceptance == b.acceptance and a.body == b.body

    def test_all_stack_profiles_render_every_family(self) -> None:
        for domain in FAMILIES:
            for stack in PROFILES:
                p = build_check_prompt("X", title="t", domain=domain,
                                       site_url="https://ex.com", stack=stack,
                                       use_kb=False)
                assert p is not None, f"{domain}/{stack}"
