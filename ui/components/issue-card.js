const _esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// Plain-language names for the fix tiers.
const TIER_LABEL = { AUTO: 'Auto-fix', 'AUTO-SAFE': 'Auto-fix', REVIEW: 'Needs review', FLAG: 'Manual' };

const FIX_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 4.8L18.7 9.6l-4.8 1.9L12 16.3l-1.9-4.8L5.3 9.6l4.8-1.9L12 3z"></path></svg>';

/**
 * @param {object} issue
 * @param {boolean} canFix  auto-fix is only offered on connected WordPress sites
 * @param {number} fixedCount  fixes already applied by the agent for this issue
 */
export function createIssueCard(issue, canFix = false, fixedCount = 0) {
  const card = document.createElement('div');
  card.className = `card issue-card`;
  card.style.borderLeft = `4px solid var(--color-${issue.severity.toLowerCase()})`;
  card.style.marginBottom = 'var(--space-2)';

  // Everything below is escaped without exception. Evidence keys/values, and
  // any per-finding text, originate in CRAWLED PAGE CONTENT — auditing a hostile
  // site would otherwise let that site run script in the auditor's browser.
  // Truncate BEFORE escaping: slicing escaped output can cut an entity in half
  // (`&lt;` → `&l`) and render mojibake.
  const ev = issue.evidence && Object.keys(issue.evidence).length
    ? Object.entries(issue.evidence).slice(0, 3)
        .map(([k, v]) => `${_esc(String(k).slice(0, 40))}: ${_esc(String(v).slice(0, 80))}`)
        .join(' · ')
    : '';

  card.innerHTML = `
    <div class="flex" style="justify-content: space-between; align-items: flex-start;">
      <div>
        <div class="flex gap-2" style="align-items: center; margin-bottom: var(--space-1);">
          <span class="badge badge-${issue.severity.toLowerCase()}">${_esc(issue.severity)}</span>
          <h3 style="margin: 0;">${_esc(issue.title)}</h3>
        </div>
        <p class="text-sm" style="margin-bottom: var(--space-1);">${_esc(issue.why_it_matters) || 'No rationale provided.'}</p>
        ${issue.recommended_fix ? `<p class="text-sm" style="margin-bottom: var(--space-1); color: var(--text-secondary);"><strong>Fix:</strong> ${_esc(issue.recommended_fix)}</p>` : ''}
        ${ev ? `<p class="text-sm mono" style="margin-bottom: var(--space-1); color: var(--text-secondary); font-size: 11px;">Evidence: ${ev}</p>` : ''}
        <div class="flex gap-2" style="align-items:center;">
          <span class="badge badge-tier">${_esc(TIER_LABEL[issue.tier] || issue.tier || '')}</span>
          <span class="text-sm" style="color: var(--text-secondary); font-weight: 500;">Affected URLs: ${issue.affected_url_ids?.length || 0}</span>
        </div>
      </div>
      <div class="flex-col gap-2" style="align-items: stretch;">
        <button class="btn btn-secondary view-issue-btn" data-id="${issue.id}">View Pages</button>
        <!-- Every finding gets a copy-pasteable prompt for the user's own coding
             agent - the fix path that works on any stack, not just connected
             WordPress. Fetched lazily so the hub doesn't render N prompts. -->
        <button class="btn btn-secondary copy-prompt-btn" data-id="${issue.id}"
                title="Copy a fix prompt for your coding agent">Copy prompt</button>
        ${fixedCount > 0
          ? `<button class="fix-btn fx-done fix-issue-btn" data-id="${issue.id}" title="Click to see what the agent fixed"><span>✓ Fixed ${fixedCount}</span></button>`
          : (issue.tier === 'FLAG'
            ? `<span class="badge badge-tier" title="Report-only - never auto-applied" style="text-align:center;">Manual only</span>`
            : (canFix
              ? `<button class="fix-btn fix-issue-btn" data-id="${issue.id}" title="Send the agent to fix every affected page">${FIX_ICON}<span>Fix</span></button>`
              : ''))}
      </div>
    </div>
  `;

  return card;
}
