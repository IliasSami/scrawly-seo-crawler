from typing import Callable, Iterable

from sentinelseo.audit.context import SiteContext
from sentinelseo.checks.registry import CheckSpec, Finding

SITE_LEVEL_REGISTRY: dict[str, tuple[CheckSpec, Callable[[SiteContext], Iterable[Finding]]]] = {}

def register_site_level(
    spec: CheckSpec,
) -> Callable[[Callable[[SiteContext], Iterable[Finding]]], Callable[[SiteContext], Iterable[Finding]]]:
    """Decorator to register a site-level check function."""

    def decorator(
        func: Callable[[SiteContext], Iterable[Finding]],
    ) -> Callable[[SiteContext], Iterable[Finding]]:
        SITE_LEVEL_REGISTRY[spec.check_id] = (spec, func)
        return func

    return decorator

def get_site_level_checks() -> dict[str, tuple[CheckSpec, Callable[[SiteContext], Iterable[Finding]]]]:
    return SITE_LEVEL_REGISTRY
