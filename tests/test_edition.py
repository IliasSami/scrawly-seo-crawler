"""Edition switch: the Free edition has no control plane, no crawl authorization
and no account code path; the managed edition keeps its defaults. Also checks the
Free-edition overlay modules that the public export swaps in."""
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from sentinelseo import edition
from sentinelseo.web import crawl_gate

ROOT = Path(__file__).resolve().parents[1]
FREE = ROOT / "editions" / "free" / "src" / "sentinelseo"

# The public Free-edition export replaces sentinelseo.edition with a free-only
# module (no control plane at all); managed-only behaviour is skipped there.
MANAGED_BUILD = hasattr(edition, "DEFAULT_CP_URL")
managed_only = pytest.mark.skipif(not MANAGED_BUILD, reason="managed edition only")
overlay_only = pytest.mark.skipif(not FREE.exists(), reason="overlay sources not in this build")


def _unset(mp: pytest.MonkeyPatch, *names: str) -> None:
    """Remove env vars so the test's own writes to them are undone afterwards too
    (a bare delenv of an absent var records nothing, so later writes would leak)."""
    for name in names:
        mp.setenv(name, "")
        mp.delenv(name)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_free_build_is_always_free() -> None:
    if MANAGED_BUILD:
        pytest.skip("this is the managed-capable build")
    assert edition.current() == "free" and edition.is_free()


class TestCrawlGate:
    def test_free_edition_never_requires_authz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SCRAWLY_EDITION", "free")
        monkeypatch.setenv("SCRAWLY_REQUIRE_AUTHZ", "1")
        assert crawl_gate.authz_required() is False

