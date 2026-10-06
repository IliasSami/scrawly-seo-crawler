// charts.js — reusable D3 chart primitives for the Scrawly dashboard.
//
// Theme contract (Milestone B): every colour is bound to a CSS custom property
// via an inline `var(--token)` value, never a resolved hex. Flipping the theme
// therefore recolours the SVG through pure CSS — no JS re-render, no getComputedStyle.
// The only reason a chart re-renders is a container width change (ResizeObserver).
//
// Each factory clears its container, draws, and wires a single ResizeObserver
// (stored on the element) so repeated calls never leak observers.

import * as d3 from 'd3';

const CHART_VARS = [
  'var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)',
  'var(--chart-5)', 'var(--chart-6)', 'var(--chart-7)', 'var(--chart-8)',
];

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---- shared tooltip (one per document, themed via .chart-tip) --------------
let _tip;
function tooltip() {
  if (!_tip) {
    _tip = document.createElement('div');
    _tip.className = 'chart-tip';
    _tip.setAttribute('role', 'tooltip');
    document.body.appendChild(_tip);
  }
  return _tip;
}
function showTip(html, ev) {
  const t = tooltip();
  t.innerHTML = html;
  t.style.opacity = '1';
  moveTip(ev);
}
function moveTip(ev) {
  const t = tooltip();
  const pad = 14;
  let x = ev.clientX + pad;
  let y = ev.clientY + pad;
  const w = t.offsetWidth, h = t.offsetHeight;
  if (x + w > window.innerWidth) x = ev.clientX - w - pad;
  if (y + h > window.innerHeight) y = ev.clientY - h - pad;
  t.style.left = `${x}px`;
  t.style.top = `${y}px`;
}
function hideTip() { if (_tip) _tip.style.opacity = '0'; }

// ---- helpers ---------------------------------------------------------------
function reset(container) {
  if (container._chartRO) { container._chartRO.disconnect(); container._chartRO = null; }
  container.innerHTML = '';
}
function observe(container, draw) {
  // Re-draw on width changes only; debounced to a frame.
  let raf = 0;
  const ro = new ResizeObserver(() => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => draw());
  });
  ro.observe(container);
  container._chartRO = ro;
}
function emptyState(container, msg) {
  reset(container);
  const d = document.createElement('div');
  d.className = 'chart-empty';
  d.textContent = msg || 'No data';
  container.appendChild(d);
}

/**
 * A compact stat tile: label, big value, optional sub-line, tone accent, and an
 * optional sparkline. Returns an element you append into a tile grid.
 */
export function statTile({ label, value, sub, tone, spark }) {
  const el = document.createElement('div');
  el.className = 'stat-tile' + (tone ? ` tone-${tone}` : '');
  el.innerHTML = `
    <div class="stat-tile-label">${esc(label)}</div>
    <div class="stat-tile-value">${esc(value)}</div>
    ${sub ? `<div class="stat-tile-sub">${esc(sub)}</div>` : ''}
    <div class="stat-tile-spark"></div>`;
  if (Array.isArray(spark) && spark.length > 1) {
    sparkline(el.querySelector('.stat-tile-spark'), {
      values: spark,
      colorVar: tone ? `var(--color-${tone})` : 'var(--accent)',
    });
  }
  return el;
}

/** Tiny inline trend line. */
export function sparkline(container, { values, colorVar = 'var(--accent)' }) {
  reset(container);
  const draw = () => {
    const w = container.clientWidth || 80;
    const h = container.clientHeight || 24;
    container.querySelector('svg')?.remove();
    const svg = d3.select(container).append('svg')
      .attr('width', w).attr('height', h).attr('class', 'chart-svg');
    const x = d3.scaleLinear().domain([0, values.length - 1]).range([1, w - 1]);
    const y = d3.scaleLinear().domain(d3.extent(values)).range([h - 2, 2]);
    const line = d3.line().x((d, i) => x(i)).y((d) => y(d)).curve(d3.curveMonotoneX);
    svg.append('path').attr('d', line(values))
      .attr('fill', 'none').style('stroke', colorVar)
      .attr('stroke-width', 1.5).attr('stroke-linecap', 'round');
  };
  draw();
  observe(container, draw);
}

/**
 * Donut chart. data: [{label, value, color}]. `color` is a CSS var string;
 * when omitted, falls back to the categorical palette.
 */
export function donut(container, { data, centerValue, centerLabel } = {}) {
  const items = (data || []).filter((d) => d.value > 0);
  if (!items.length) return emptyState(container, 'No data');
  reset(container);
  const draw = () => {
    container.querySelector('svg')?.remove();
    const w = container.clientWidth || 240;
    const h = Math.max(160, Math.min(220, w * 0.7));
    const r = Math.min(w, h) / 2;
    const thickness = Math.max(16, r * 0.34);
    const svg = d3.select(container).append('svg')
      .attr('width', w).attr('height', h).attr('class', 'chart-svg');
    const g = svg.append('g').attr('transform', `translate(${w / 2},${h / 2})`);
    const pie = d3.pie().value((d) => d.value).sort(null).padAngle(0.02);
    const arc = d3.arc().innerRadius(r - thickness).outerRadius(r).cornerRadius(3);
    const total = d3.sum(items, (d) => d.value);
    g.selectAll('path').data(pie(items)).join('path')
      .attr('d', arc)
      .style('fill', (d, i) => d.data.color || CHART_VARS[i % CHART_VARS.length])
      .style('stroke', 'var(--bg-surface)').style('stroke-width', 2)
      .style('cursor', 'default')
      .on('mouseenter', (ev, d) => showTip(
        `<b>${esc(d.data.label)}</b><span>${d.data.value} · ${Math.round(d.data.value / total * 100)}%</span>`, ev))
      .on('mousemove', moveTip).on('mouseleave', hideTip);
    if (centerValue != null) {
      g.append('text').attr('class', 'donut-center-value').attr('text-anchor', 'middle')
        .attr('dy', centerLabel ? '-0.05em' : '0.35em').text(centerValue);
    }
    if (centerLabel) {
      g.append('text').attr('class', 'donut-center-label').attr('text-anchor', 'middle')
        .attr('dy', '1.4em').text(centerLabel);
    }
  };
  draw();
  observe(container, draw);
}

/**
 * Horizontal bar chart. data: [{label, value, color?}]. Good for ranked
 * categories / segments. Bars use the palette unless a color is supplied.
 */
export function bars(container, { data, colorVar, formatValue } = {}) {
  const items = (data || []).filter((d) => d.value > 0);
  if (!items.length) return emptyState(container, 'No data');
  const fmt = formatValue || ((v) => v);
  reset(container);
  const draw = () => {
    container.querySelector('svg')?.remove();
    const w = container.clientWidth || 280;
    const rowH = 30, gap = 8;
    const h = items.length * (rowH + gap);
    const labelW = Math.min(140, Math.max(70, w * 0.34));
    const valW = 44;
    const barX = labelW + 8;
    const barMax = Math.max(20, w - barX - valW);
    const max = d3.max(items, (d) => d.value) || 1;
    const x = d3.scaleLinear().domain([0, max]).range([0, barMax]);
    const svg = d3.select(container).append('svg')
      .attr('width', w).attr('height', h).attr('class', 'chart-svg');
    const rows = svg.selectAll('g.bar-row').data(items).join('g')
      .attr('class', 'bar-row')
      .attr('transform', (d, i) => `translate(0,${i * (rowH + gap)})`);
    rows.append('text').attr('class', 'bar-label')
      .attr('x', 0).attr('y', rowH / 2).attr('dy', '0.32em')
      .attr('width', labelW).text((d) => d.label)
      .each(function () { truncate(this, labelW); });
    rows.append('rect').attr('class', 'bar-track')
      .attr('x', barX).attr('y', 4).attr('rx', 4)
      .attr('width', barMax).attr('height', rowH - 8)
      .style('fill', 'var(--chart-track)');
    rows.append('rect').attr('class', 'bar-fill')
      .attr('x', barX).attr('y', 4).attr('rx', 4)
      .attr('height', rowH - 8)
      .style('fill', (d, i) => d.color || colorVar || CHART_VARS[i % CHART_VARS.length])
      .attr('width', 0)
      .on('mouseenter', (ev, d) => showTip(`<b>${esc(d.label)}</b><span>${fmt(d.value)}</span>`, ev))
      .on('mousemove', moveTip).on('mouseleave', hideTip)
      .transition().duration(450).ease(d3.easeCubicOut)
      .attr('width', (d) => Math.max(2, x(d.value)));
    rows.append('text').attr('class', 'bar-value')
      .attr('x', w).attr('y', rowH / 2).attr('dy', '0.32em')
      .attr('text-anchor', 'end').text((d) => fmt(d.value));
  };
  draw();
  observe(container, draw);
}

/** Vertical histogram. data: [{label, value}]. For crawl-depth distribution. */
export function histogram(container, { data, colorVar = 'var(--accent)', formatValue } = {}) {
  const items = data || [];
  if (!items.length || d3.sum(items, (d) => d.value) === 0) return emptyState(container, 'No data');
  const fmt = formatValue || ((v) => v);
  reset(container);
  const draw = () => {
    container.querySelector('svg')?.remove();
    const w = container.clientWidth || 280;
    const h = 170;
    const m = { top: 12, right: 4, bottom: 26, left: 4 };
    const iw = w - m.left - m.right;
    const ih = h - m.top - m.bottom;
    const svg = d3.select(container).append('svg')
      .attr('width', w).attr('height', h).attr('class', 'chart-svg');
    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`);
    const x = d3.scaleBand().domain(items.map((d) => d.label)).range([0, iw]).padding(0.28);
    const max = d3.max(items, (d) => d.value) || 1;
    const y = d3.scaleLinear().domain([0, max]).range([ih, 0]).nice();
    const col = g.selectAll('g.col').data(items).join('g').attr('class', 'col');
    col.append('rect')
      .attr('x', (d) => x(d.label)).attr('width', x.bandwidth())
      .attr('y', ih).attr('height', 0).attr('rx', 3)
      .style('fill', colorVar).style('cursor', 'default')
      .on('mouseenter', (ev, d) => showTip(`<b>${esc(d.label)}</b><span>${fmt(d.value)}</span>`, ev))
      .on('mousemove', moveTip).on('mouseleave', hideTip)
      .transition().duration(450).ease(d3.easeCubicOut)
      .attr('y', (d) => y(d.value)).attr('height', (d) => ih - y(d.value));
    col.append('text').attr('class', 'col-value')
      .attr('x', (d) => x(d.label) + x.bandwidth() / 2)
      .attr('y', (d) => y(d.value) - 5).attr('text-anchor', 'middle')
      .text((d) => (d.value > 0 ? d.value : ''));
    col.append('text').attr('class', 'col-label')
      .attr('x', (d) => x(d.label) + x.bandwidth() / 2)
      .attr('y', ih + 18).attr('text-anchor', 'middle').text((d) => d.label);
  };
  draw();
  observe(container, draw);
}

/**
 * A single stacked horizontal bar with a legend below — compact way to show a
 * severity distribution. segments: [{label, value, color}].
 */
export function stackedBar(container, { segments } = {}) {
  const items = (segments || []).filter((d) => d.value > 0);
  reset(container);
  const total = d3.sum(items, (d) => d.value);
  if (!total) return emptyState(container, 'No issues 🎉');

  const track = document.createElement('div');
  track.className = 'stacked-bar-track';
  items.forEach((s) => {
    const seg = document.createElement('div');
    seg.className = 'stacked-bar-seg';
    seg.style.flexGrow = String(s.value);
    seg.style.background = s.color;
    seg.title = `${s.label}: ${s.value}`;
    seg.addEventListener('mouseenter', (ev) => showTip(
      `<b>${esc(s.label)}</b><span>${s.value} · ${Math.round(s.value / total * 100)}%</span>`, ev));
    seg.addEventListener('mousemove', moveTip);
    seg.addEventListener('mouseleave', hideTip);
    track.appendChild(seg);
  });

  const legend = document.createElement('div');
  legend.className = 'stacked-bar-legend';
  items.forEach((s) => {
    const li = document.createElement('div');
    li.className = 'legend-item';
    li.innerHTML = `<span class="legend-dot" style="background:${s.color}"></span>` +
      `<span class="legend-label">${esc(s.label)}</span>` +
      `<span class="legend-value">${s.value}</span>`;
    legend.appendChild(li);
  });

  container.appendChild(track);
  container.appendChild(legend);
}

// Truncate an SVG <text> node to fit maxWidth with an ellipsis.
function truncate(node, maxWidth) {
  const full = node.textContent;
  if (node.getComputedTextLength() <= maxWidth) return;
  let t = full;
  while (t.length > 1 && node.getComputedTextLength() > maxWidth) {
    t = t.slice(0, -1);
    node.textContent = t + '…';
  }
}
