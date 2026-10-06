"""The generated prompts are run by coding agents against production sites.

That makes two properties non-negotiable and worth testing explicitly:
  1. They must be stack-CORRECT — naming a file that does not exist on the
     detected platform sends the agent to create dead config.
  2. They must be SAFE — never carrying a destructive command or a secret.
"""
from __future__ import annotations

from sentinelseo.prompts import (
    AGENTIC_SPECS,
    SAFETY_CONSTRAINTS,
    PromptContext,
    build_agentic_prompt,
    render_prompt,
    resolve_stack,
)
from sentinelseo.prompts.stacks import PROFILES


class TestStackResolution:
    def test_known_stacks_resolve(self) -> None:
        assert resolve_stack("wordpress").key == "wordpress"
        assert resolve_stack("nextjs").key == "nextjs"
        assert resolve_stack("Shopify").key == "shopify"

    def test_aliases_map_to_the_right_profile(self) -> None:
        assert resolve_stack("woocommerce").key == "wordpress"
        assert resolve_stack("next.js").key == "nextjs"
        assert resolve_stack("nuxt").key == "nextjs"
        assert resolve_stack("jekyll").key == "static"

    def test_unknown_and_empty_fall_back_to_generic(self) -> None:
        assert resolve_stack("bespoke-cms").key == "generic"
        assert resolve_stack("").key == "generic"
        assert resolve_stack(None).key == "generic"

    def test_every_profile_defines_all_artefact_locations(self) -> None:
        for key, p in PROFILES.items():
            for artefact in ("robots", "sitemap", "headers", "static", "well_known"):
                assert p.location(artefact), f"{key} missing location for {artefact}"


class TestPromptRendering:
    def test_every_agentic_probe_has_a_spec(self) -> None:
        assert len(AGENTIC_SPECS) >= 22

    def test_all_specs_render_for_all_stacks(self) -> None:
        for pid in AGENTIC_SPECS:
            for stack in PROFILES:
                p = build_agentic_prompt(pid, site_url="https://ex.com", stack=stack)
                assert p is not None and len(p.text) > 200, f"{pid}/{stack}"

    def test_prompt_contains_all_required_sections(self) -> None:
        p = build_agentic_prompt("AGT.ROBOTS", site_url="https://ex.com",
                                 stack="wordpress")
        assert p is not None
        for section in ("## Task", "## Problem", "## What we observed",
                        "## Where to make the change", "## Acceptance criteria",
                        "## Verify", "## Constraints"):
            assert section in p.text, f"missing {section}"

    def test_domain_is_substituted_into_verify_commands(self) -> None:
        p = build_agentic_prompt("AGT.ROBOTS", site_url="https://ex.com", stack="hugo")
        assert p is not None
        assert "ex.com" in p.text
        assert "<domain>" not in p.text.split("## Verify")[1]

    def test_unknown_probe_returns_none(self) -> None:
        assert build_agentic_prompt("AGT.NOPE", site_url="https://ex.com") is None

    def test_evidence_is_included(self) -> None:
        p = build_agentic_prompt("AGT.AI_BOTS", site_url="https://ex.com",
                                 stack="nextjs", evidence={"bots": ["gptbot"]})
        assert p is not None and "gptbot" in p.text

    def test_affected_urls_are_listed_and_capped(self) -> None:
        urls = [f"https://ex.com/p{i}" for i in range(50)]
        spec = AGENTIC_SPECS["AGT.ROBOTS"]
        out = render_prompt(spec, PromptContext(site_url="https://ex.com",
                                                stack="generic",
                                                affected_urls=urls))
        assert "https://ex.com/p0" in out.text
        assert "and 35 more" in out.text, "long URL lists must be truncated"


class TestStackCorrectness:
    """The whole point: the prompt must name the right file for the platform."""

    def test_robots_location_differs_per_stack(self) -> None:
        def where(stack: str) -> str:
            p = build_agentic_prompt("AGT.ROBOTS", site_url="https://ex.com",
                                     stack=stack)
            assert p is not None
            return p.text.split("## Where to make the change")[1]

        assert "functions.php" in where("wordpress") or "mu-plugin" in where("wordpress")
        assert "app/robots.ts" in where("nextjs")
        assert "robots.txt.liquid" in where("shopify")
        assert "static/robots.txt" in where("hugo")

    def test_nextjs_prompt_warns_about_route_vs_static_conflict(self) -> None:
        p = build_agentic_prompt("AGT.ROBOTS", site_url="https://ex.com",
                                 stack="nextjs")
        assert p is not None
        assert "overrides a static file" in p.text

    def test_shopify_admits_wellknown_is_not_possible(self) -> None:
        """Better to state the platform limit than invent an impossible path."""
        p = build_agentic_prompt("AGT.MCP_CARD", site_url="https://ex.com",
                                 stack="shopify")
        assert p is not None
        assert "CANNOT" in p.text or "does not allow" in p.text

    def test_wordpress_prompt_warns_against_editing_core(self) -> None:
        p = build_agentic_prompt("AGT.ROBOTS", site_url="https://ex.com",
                                 stack="wordpress")
        assert p is not None
        assert "core files" in p.text


class TestPromptSafety:
    def test_safety_constraints_appear_in_every_prompt(self) -> None:
        for pid in AGENTIC_SPECS:
            p = build_agentic_prompt(pid, site_url="https://ex.com", stack="generic")
            assert p is not None
            assert SAFETY_CONSTRAINTS[0] in p.text, pid
            assert "Never commit secrets" in p.text, pid

    def test_no_prompt_contains_a_destructive_command(self) -> None:
        banned = ("rm -rf", "DROP TABLE", "DROP DATABASE", "mkfs",
                  "chmod 777", "git push --force", "> /dev/sda", "TRUNCATE TABLE")
        for pid in AGENTIC_SPECS:
            for stack in PROFILES:
                p = build_agentic_prompt(pid, site_url="https://ex.com", stack=stack)
                assert p is not None
                for bad in banned:
                    assert bad not in p.text, f"{pid}/{stack} contains {bad!r}"

    def test_money_touching_probes_carry_an_extra_warning(self) -> None:
        for pid in ("AGT.X402", "AGT.MPP", "AGT.UCP", "AGT.ACP"):
            p = build_agentic_prompt(pid, site_url="https://ex.com", stack="generic")
            assert p is not None
            assert "money" in p.text.lower(), f"{pid} must flag financial risk"

    def test_private_key_publication_is_explicitly_forbidden(self) -> None:
        p = build_agentic_prompt("AGT.WEB_BOT_AUTH", site_url="https://ex.com",
                                 stack="generic")
        assert p is not None
        assert "private key" in p.text.lower()

    def test_dns_probe_flags_that_it_changes_dns(self) -> None:
        p = build_agentic_prompt("AGT.DNS_AID", site_url="https://ex.com",
                                 stack="generic")
        assert p is not None
        assert "DNS" in p.text


class TestSpecQuality:
    def test_every_spec_has_testable_acceptance_criteria(self) -> None:
        for pid, spec in AGENTIC_SPECS.items():
            assert spec.acceptance, f"{pid} has no acceptance criteria"
            assert len(spec.acceptance) >= 2, f"{pid} acceptance is too thin"

    def test_every_spec_has_a_problem_statement_and_verification(self) -> None:
        for pid, spec in AGENTIC_SPECS.items():
            assert len(spec.problem) > 40, f"{pid} problem statement is too vague"
            assert spec.verify, f"{pid} has no verification step"

    def test_spec_ids_match_their_keys(self) -> None:
        for pid, spec in AGENTIC_SPECS.items():
            assert spec.check_id == pid
