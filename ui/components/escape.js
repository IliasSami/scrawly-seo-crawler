// ui/components/escape.js
// Escape text for safe use inside HTML markup and attribute values. Anything that
// can come from a crawled site (titles, URLs, headings) or from the server must go
// through this before it is placed in an innerHTML template.
const MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => MAP[c]);
}
