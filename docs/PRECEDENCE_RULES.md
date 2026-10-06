# Precedence Rules

This document implements the precedence table from the "Aggregation" section of the detection logic. It is structured as a declarative, testable ruleset to prevent double-reporting of issues.

## Declarative Ruleset

```yaml
rules:
  - rule_id: "R1_HTTP_ERRORS_SUPPRESS_ONPAGE"
    suppressor_check_ids: ["B01", "B02"]
    suppressed_domains: ["D", "E", "H", "J"]
    condition: "same_url"
    action: "suppress"
    description: "If a page returns a 4xx/5xx error, it cannot be meaningfully audited for on-page content issues. Drop all findings in domains D, E, H, and J for this URL."

  - rule_id: "R2_NOINDEX_DOWNGRADES_OPPORTUNITIES"
    suppressor_check_ids: ["A04", "A05"]
    suppressed_check_ids: ["D03", "D04", "D09", "D10"]
    condition: "same_url"
    action: "downgrade_to_info"
    description: "If a page is noindex, downgrade title/meta pixel width opportunities to INFO."

  - rule_id: "R3_EXACT_DUP_SUPPRESSES_NEAR_DUP"
    suppressor_check_ids: ["E01"]
    suppressed_check_ids: ["E02"]
    condition: "same_url_pair"
    action: "suppress"
    description: "An exact duplicate is inherently a near duplicate. Do not report E02 if E01 fires for the exact same URL pair."

  - rule_id: "R4_CANONICAL_REDIRECT_SUPPRESSES_C04"
    suppressor_check_ids: ["B10"]
    suppressed_check_ids: ["C04"]
    condition: "same_url"
    action: "suppress"
    description: "B10 (Canonical -> redirect) is a more specific/descriptive version of C04. Suppress C04 to prevent duplicate reporting."

  - rule_id: "R5_BLOCKED_RESOURCES_DEDUPLICATION"
    suppressor_check_ids: ["A02"]
    suppressed_check_ids: ["L03"]
    condition: "same_url"
    action: "suppress"
    description: "A02 and L03 flag the same underlying defect (resources blocked by robots.txt affecting rendering). Emit once under A02."
```
