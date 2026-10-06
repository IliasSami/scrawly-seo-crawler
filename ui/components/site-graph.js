// ui/components/site-graph.js
// Advanced, interactive site-architecture visualization.
// Layouts:
//   • arch       — Architecture map (DEFAULT): a Screaming-Frog-style
//                  force-directed diagram of the true information architecture.
//                  Home is pinned at the centre; sections/categories fan out as
//                  organic branches; posts and pages cluster as leaves at the
//                  ends. Topology comes from the URL directory hierarchy (every
//                  section shown, even implicit ones), NOT the crawl click-path.
//   • force3d    — the same architecture hierarchy in 3D (top-down DAG tree).
//   • directory  — the same hierarchy as a tidy left-to-right branching tree.
//   • force      — radial crawl map (home centre, parent = shortest click path).
//   • tree       — crawl-depth tree (BFS parent = shortest click path).
//   • clusters   — content clusters: circle-packing of the directory hierarchy
//                  (pages nested inside their sections, sized by a metric).
//   • redirects  — redirect chains.
// Nodes are sizeable (authority / inlinks / words) and colourable (indexability
// / status / issues / depth); broken, canonicalized and orphan pages flagged.
// Hover = rich tooltip + neighbour highlight; click = open the detail drawer.
import { esc } from './escape.js';
import * as d3 from 'd3';
// 3d-force-graph (three.js) is heavy — lazy-loaded in _force3d() so it only
// downloads when the user actually opens the 3D layout.

const SEV_COLOR = { Critical: '#dc2626', High: '#f59e0b', Medium: '#eab308', Low: '#3b82f6', Info: '#94a3b8' };
const OK = '#22c55e', RED = '#ef4444', ORANGE = '#f59e0b', PURPLE = '#8b5cf6', GRAY = '#64748b';
const pathOf = (u) => { try { const x = new URL(u); return (x.pathname + x.search) || '/'; } catch { return u; } };
const seg0 = (u) => { try { const p = new URL(u).pathname.split('/').filter(Boolean); return p[0] || '(root)'; } catch { return '(root)'; } };

export class SiteGraph {
  constructor(container, { onNodeClick } = {}) {
    this.container = container;
    this.onNodeClick = onNodeClick || (() => {});
    this.data = { nodes: [], edges: [] };
    this.layout = 'arch';
    this.sizeBy = 'pagerank';
    this.colorBy = 'indexable';
    this.query = '';
    this.sim = null;
    this._shell();
  }

  setData(graph) {
    this.data = { nodes: (graph.nodes || []).map(n => ({ ...n })), edges: graph.edges || [] };
    this._segColor = null;  // segment palette is derived from this crawl's nodes
    this.render();
  }

  _shell() {
    this.container.innerHTML = `
      <div class="sg-controls">
        <div class="sg-ctl"><label>Layout</label>
          <select class="sg-layout">
            <option value="arch">Architecture map (force-directed)</option>
            <option value="force3d">Architecture map (3D)</option>
            <option value="directory">Architecture tree (branches)</option>
            <option value="force">Crawl map (radial)</option>
            <option value="tree">Crawl-depth tree</option>
            <option value="clusters">Content clusters</option>
            <option value="redirects">Redirect chains</option>
          </select></div>
        <div class="sg-ctl sg-metric-ctl"><label>Size by</label>
          <select class="sg-size">
            <option value="pagerank">Authority (PageRank)</option>
            <option value="inlinks">Inlinks</option>
            <option value="words">Word count</option>
            <option value="uniform">Uniform</option>
          </select></div>
        <div class="sg-ctl sg-color-ctl"><label>Colour by</label>
          <select class="sg-color">
            <option value="indexable">Indexability</option>
            <option value="status">Status code</option>
            <option value="issues">Issues (severity)</option>
            <option value="depth">Crawl depth</option>
            <option value="segment">Segment</option>
          </select></div>
        <div class="sg-ctl sg-grow"><input class="sg-search" type="text" placeholder="Search / highlight URLs…"></div>
      </div>
      <div class="sg-stats"></div>
      <div class="sg-stage"><div class="sg-canvas"></div><div class="sg-legend"></div></div>
      <div class="sg-tip" style="display:none"></div>`;
    const $ = (s) => this.container.querySelector(s);
    this.stage = $('.sg-canvas'); this.tip = $('.sg-tip');
    $('.sg-layout').addEventListener('change', e => { this.layout = e.target.value; this.render(); });
    $('.sg-size').addEventListener('change', e => { this.sizeBy = e.target.value; this.render(); });
    $('.sg-color').addEventListener('change', e => {
      this.colorBy = e.target.value;
      if (this.layout === 'force' || this.layout === 'arch') { this._recolor(); this._legend(); } else this.render();
    });
    $('.sg-search').addEventListener('input', e => { this.query = e.target.value.toLowerCase().trim(); this._applySearch(); });
  }

  _msg(html) { this.stage.innerHTML = `<div class="sg-empty">${html}</div>`; }

  render() {
    // Control relevance: size + colour apply to every node-based layout
    // (architecture tree, 3D, link graph, crawl tree, clusters) — not redirects.
    const is3d = this.layout === 'force3d';
    const showSize = this.layout !== 'redirects';
    const showColor = this.layout !== 'redirects' && this.layout !== 'clusters';
    const mc = this.container.querySelector('.sg-metric-ctl');
    const cc = this.container.querySelector('.sg-color-ctl');
    if (mc) mc.style.visibility = showSize ? 'visible' : 'hidden';
    if (cc) cc.style.visibility = showColor ? 'visible' : 'hidden';

    if (this.sim) { this.sim.stop(); this.sim = null; }
    // Tear down any live 3D scene before swapping layouts (stops its render loop).
    if (this._graph3d) { try { this._graph3d.pauseAnimation(); this._graph3d._destructor?.(); } catch { /* */ } this._graph3d = null; }
    this.stage.innerHTML = '';
    this._node = null; this._link = null; this._searchSel = null; this._searchId = null;
    const n = this.data.nodes.length;
    if (!n) return this._msg('No crawled pages to graph yet.');
    this._stats();
    if (this.layout === 'redirects') return this._redirects();
    if (this.layout === 'arch') return this._archForce();
    if (this.layout === 'tree') return this._tree(this._depthHierarchy());
    if (this.layout === 'directory') return this._tree(this._dirHierarchy());
    if (this.layout === 'clusters') return this._clusters();
    if (is3d) return this._force3d();
    return this._force();
  }

  // ---- crawl tree (parent = shortest click-path page that links here) ----
  _crawlTreeLinks() {
    const adj = {}; this.data.edges.forEach(e => (adj[e.source] = adj[e.source] || []).push(e.target));
    const byDepth = [...this.data.nodes].sort((a, b) => (a.depth ?? 99) - (b.depth ?? 99));
    const root = byDepth[0];
    const parent = { [root.id]: null }; const q = [root.id];
    while (q.length) { const u = q.shift(); (adj[u] || []).forEach(v => { if (!(v in parent)) { parent[v] = u; q.push(v); } }); }
    // Pages the BFS never reached (orphans) still attach to home so they show.
    this.data.nodes.forEach(n => { if (!(n.id in parent)) parent[n.id] = (n.id === root.id ? null : root.id); });
    const links = [];
    for (const n of this.data.nodes) { const p = parent[n.id]; if (p != null) links.push({ source: p, target: n.id }); }
    return { links, rootId: root.id };
  }

  // ---- metrics ----
  _sizeVal(nodeAttr) {
    const key = { pagerank: 'pagerank', inlinks: 'inlinks', words: 'words' }[this.sizeBy];
    if (!key) return 7;
    const vals = this.data.nodes.map(d => d[key] || 0);
    const max = Math.max(1, ...vals);
    return 5 + 15 * Math.sqrt((nodeAttr?.[key] || 0) / max);
  }
  _packVal(n) {
    const key = { pagerank: 'pagerank', inlinks: 'inlinks', words: 'words' }[this.sizeBy];
    return key ? Math.max(1, n[key] || 0) : 1;
  }
  _segScale() {
    // Stable colour per segment name; unsegmented pages stay neutral grey.
    if (!this._segColor) {
      const names = [...new Set(this.data.nodes.map(n => n.segment).filter(Boolean))].sort();
      this._segColor = d3.scaleOrdinal(names, d3.schemeTableau10);
    }
    return this._segColor;
  }
  _color(d) {
    if (this.colorBy === 'segment') return d.segment ? this._segScale()(d.segment) : GRAY;
    if (d.broken) return RED;
    if (this.colorBy === 'issues') return d.severity ? SEV_COLOR[d.severity] : (d.indexable ? OK : GRAY);
    if (this.colorBy === 'status') {
      const s = d.status || 0;
      return s >= 400 ? RED : s >= 300 ? ORANGE : s >= 200 ? OK : GRAY;
    }
    if (this.colorBy === 'depth') {
      const dm = Math.max(1, ...this.data.nodes.map(x => x.depth || 0));
      return d3.interpolateBlues(0.25 + 0.7 * ((d.depth || 0) / dm));
    }
    return d.indexable ? OK : RED;
  }
  _stroke(d) { return d.canonicalized ? PURPLE : (d.orphan ? '#eab308' : '#ffffff'); }

  _stats() {
    const N = this.data.nodes;
    const broken = N.filter(d => d.broken).length;
    const orphan = N.filter(d => d.orphan).length;
    const nonidx = N.filter(d => !d.indexable).length;
    const withIssues = N.filter(d => d.issues > 0).length;
    const maxD = Math.max(0, ...N.map(d => d.depth || 0));
    const chip = (label, v, cls = '') => `<span class="sg-chip ${cls}">${v}<small>${label}</small></span>`;
    this.container.querySelector('.sg-stats').innerHTML =
      chip('pages', N.length) + chip('links', this.data.edges.length) +
      chip('max depth', maxD) + chip('with issues', withIssues, withIssues ? 'warn' : '') +
      chip('non-indexable', nonidx, nonidx ? 'warn' : '') +
      chip('orphans', orphan, orphan ? 'bad' : '') + chip('broken', broken, broken ? 'bad' : '');
  }

  _legend() {
    const box = this.container.querySelector('.sg-legend');
    if (this.layout === 'clusters') {
      const cats = this._catScale ? this._catScale.domain() : [];
      box.innerHTML = `<div class="sg-leg sg-note">Content sections (top-level paths)</div>` +
        cats.map(c => `<div class="sg-leg"><span class="sg-sw sg-dot" style="background:${this._catScale(c)}"></span>/${c === '(root)' ? '' : esc(c)}</div>`).join('') +
        `<div class="sg-leg-sep"></div><div class="sg-leg sg-note">Nested = hierarchy · size = ${this.sizeBy === 'uniform' ? 'equal' : this.sizeBy}</div>`;
      return;
    }
    const row = (c, t, shape = 'dot') => `<div class="sg-leg"><span class="sg-sw sg-${shape}" style="background:${c}"></span>${t}</div>`;
    let items = '';
    if (this.colorBy === 'indexable') items = row(OK, 'Indexable') + row(RED, 'Non-indexable / broken');
    else if (this.colorBy === 'status') items = row(OK, '2xx') + row(ORANGE, '3xx redirect') + row(RED, '4xx/5xx');
    else if (this.colorBy === 'issues') items = Object.entries(SEV_COLOR).map(([k, c]) => row(c, k)).join('') + row(OK, 'No issues');
    else if (this.colorBy === 'segment') {
      const names = this._segScale().domain();
      items = names.length
        ? names.map(n => row(this._segScale()(n), esc(n))).join('') + row(GRAY, 'Unsegmented')
        : `<div class="sg-leg sg-note">No segments defined - add rules under Configuration → Segments.</div>`;
    }
    else items = row(d3.interpolateBlues(0.4), 'Shallow') + row(d3.interpolateBlues(0.95), 'Deep');
    if (this.layout === 'arch') items = `<div class="sg-leg sg-note">Home centre · sections branch out by URL architecture</div>` + `<div class="sg-leg"><span class="sg-sw sg-ring" style="border-color:#94a3b8;background:var(--bg-surface)"></span>Section (hollow)</div>` + items;
    else if (this.layout === 'force') items = `<div class="sg-leg sg-note">Home centre · fans out by crawl path</div>` + items;
    else if (this.layout === 'force3d') items = `<div class="sg-leg sg-note">3D · drag to rotate, scroll to zoom</div>` + items;
    items += `<div class="sg-leg-sep"></div>` +
      `<div class="sg-leg"><span class="sg-sw sg-ring" style="border-color:${PURPLE}"></span>Canonicalized</div>` +
      `<div class="sg-leg"><span class="sg-sw sg-ring" style="border-color:#eab308"></span>Orphan (0 inlinks)</div>` +
      `<div class="sg-leg sg-note">Size = ${this.sizeBy === 'uniform' ? 'fixed' : this.sizeBy}</div>`;
    box.innerHTML = items;
  }

  // ---- architecture map: Screaming-Frog-style force-directed diagram ----
  // Flat node/link data for the force layout, derived from the URL DIRECTORY
  // hierarchy (architecture, not crawl path). Every section is a node — even
  // implicit ones with no page of their own — so the whole hierarchy shows.
  // Page metrics are spread onto each node so _color / _sizeVal / _stroke /
  // _showTip work directly; the topology id is the URL path (unique per node).
  _dirForceData() {
    const rootH = this._dirHierarchy();
    const nodes = rootH.descendants().map(d => {
      const p = d.data.node || null;
      const base = p ? { ...p } : {};
      base.id = d.data.id;                                   // topology id (URL path)
      base.name = d.data.name;                              // segment label
      base.isDir = !p;                                       // section vs real page
      base.hdepth = d.depth;                                // hierarchy depth
      base.leaves = d.descendants().filter(x => x.data.node).length;
      base.pageId = p ? p.id : null;                        // real crawl-node id
      return base;
    });
    const links = rootH.links().map(l => ({ source: l.source.data.id, target: l.target.data.id }));
    return { nodes, links, rootId: rootH.data.id };
  }

  // Home pinned centre; sections branch out as organic arms; pages fan out as
  // leaves at the ends. Sections are hollow hubs sized by pages-beneath; pages
  // are solid, sized + coloured by the chosen metric.
  _archForce() {
    const W = this.stage.clientWidth || 900, H = this.stage.clientHeight || 560;
    const cx = W / 2, cy = H / 2;
    const { nodes, links: rawLinks, rootId } = this._dirForceData();
    this._rootId = rootId;
    const byId = new Map(nodes.map(n => [n.id, n]));
    const links = rawLinks.map(l => ({ ...l }));
    // Fan each hub's children into a ring wide enough to hold them all.
    const kids = {}; links.forEach(l => { kids[l.source] = (kids[l.source] || 0) + 1; });
    const rOf = d => d.id === rootId
      ? Math.max(10, this._sizeVal(d))
      : (d.isDir ? Math.max(5, 4 + Math.sqrt(d.leaves || 1) * 1.7) : Math.max(4, this._sizeVal(d)));
    const hdepthOf = t => (byId.get(typeof t === 'object' ? t.id : t) || {}).hdepth || 1;

    const zoomB = d3.zoom().scaleExtent([0.03, 6]).on('zoom', ev => g.attr('transform', ev.transform));
    const svg = d3.select(this.stage).append('svg').attr('width', W).attr('height', H).call(zoomB);
    const g = svg.append('g');

    const link = g.append('g').attr('stroke', '#8a93a5').attr('stroke-opacity', 0.5)
      .selectAll('line').data(links).join('line')
      .attr('stroke-width', d => Math.max(0.6, 2.2 - hdepthOf(d.target) * 0.45));  // trunk → twig taper

    const sim = this.sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).strength(0.9)
        .distance(l => { const c = kids[l.source.id || l.source] || 1; return Math.max(38, (c * 26) / (2 * Math.PI)) + rOf(l.target || {}); }))
      .force('charge', d3.forceManyBody().strength(-60).distanceMax(900).theta(0.85))
      .force('collide', d3.forceCollide().radius(d => rOf(d) + 5).iterations(3))
      .force('center', d3.forceCenter(cx, cy).strength(0.05));
    const rootNode = byId.get(rootId);
    if (rootNode) { rootNode.fx = cx; rootNode.fy = cy; }

    const node = g.append('g').selectAll('circle').data(nodes).join('circle')
      .attr('r', rOf)
      .attr('fill', d => d.isDir ? 'var(--bg-surface)' : this._color(d))
      .attr('stroke', d => d.id === rootId ? 'var(--accent)' : (d.isDir ? '#94a3b8' : this._stroke(d)))
      .attr('stroke-width', d => d.id === rootId ? 3 : (d.isDir ? 2 : ((d.canonicalized || d.orphan) ? 2 : 1.2)))
      .style('cursor', d => d.isDir ? 'default' : 'pointer')
      .call(this._drag(sim))
      .on('mouseover', (ev, d) => { this._hover(d, node, link); if (d.isDir) this._showDirTip(ev, d); else this._showTip(ev, d); })
      .on('mousemove', ev => this._moveTip(ev))
      .on('mouseout', () => { this._unhover(node, link); this.tip.style.display = 'none'; })
      .on('click', (ev, d) => { if (!d.isDir && d.pageId) { ev.stopPropagation(); this.onNodeClick(d.pageId); } });

    // Labels: home + every section always; pages only when the map stays legible
    // (otherwise their titles live in the hover tooltip). Non-interactive.
    const labelPages = nodes.length <= 60;
    const label = g.append('g').style('pointer-events', 'none').selectAll('text').data(nodes).join('text')
      .attr('class', 'sg-arch-label').attr('text-anchor', 'middle')
      .attr('font-size', d => d.id === rootId ? 12 : (d.isDir ? 11 : 9))
      .attr('font-weight', d => d.id === rootId ? 700 : (d.isDir ? 600 : 400))
      .attr('dy', d => -rOf(d) - 4)
      .text(d => {
        if (!d.isDir && !labelPages) return '';
        const t = d.id === rootId ? 'Home' : (d.isDir ? '/' + d.name : (d.name || pathOf(d.id)));
        return t.length > 24 ? t.slice(0, 24) + '…' : t;
      });

    this._node = node; this._link = link; this._adj = this._adjacency(links);
    this._baseLinkOp = 0.5; this._searchSel = node; this._searchId = d => d.pageId || d.id;

    const ticked = () => {
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      node.attr('cx', d => d.x).attr('cy', d => d.y);
      label.attr('x', d => d.x).attr('y', d => d.y);
    };
    sim.on('tick', ticked);
    sim.alpha(1); for (let i = 0; i < 320; i++) sim.tick();
    ticked();
    this._fitToView(svg, g, zoomB, W, H);
    sim.alphaDecay(0.045).alpha(0.12).restart();
    this._legend();
    this._applySearch();
  }

  _showDirTip(ev, d) {
    this.tip.innerHTML = `<div class="sg-tip-h mono"><span class="sg-tip-url">${d.id === this._rootId ? 'Home' : '/' + esc(d.name)}</span></div>` +
      `<div class="sg-tip-r"><span>Type</span><b>Section</b></div>` +
      `<div class="sg-tip-r"><span>Pages under</span><b>${d.leaves}</b></div>`;
    this.tip.style.display = 'block'; this._moveTip(ev);
  }

  // ---- force: hierarchical crawl-tree diagram (Screaming-Frog style) ----
  // The layout is driven by the CRAWL TREE (each page linked to the shallowest
  // page that reached it), not the full hyperlink graph — so home sits central
  // and pages/sub-pages fan out from their parent in organic clusters.
  _force() {
    const W = this.stage.clientWidth || 900, H = this.stage.clientHeight || 560;
    const cx = W / 2, cy = H / 2;
    const nodes = this.data.nodes;
    const byId = new Map(nodes.map(n => [n.id, n]));
    const { links: treeLinks, rootId } = this._crawlTreeLinks();
    const links = treeLinks.map(l => ({ ...l }));
    // Children per parent → scale repulsion so big fans don't overlap.
    const kids = {}; links.forEach(l => { kids[l.source] = (kids[l.source] || 0) + 1; });

    const zoomB = d3.zoom().scaleExtent([0.03, 6]).on('zoom', ev => g.attr('transform', ev.transform));
    const svg = d3.select(this.stage).append('svg').attr('width', W).attr('height', H).call(zoomB);
    const g = svg.append('g');

    const link = g.append('g').attr('stroke', '#8a93a5').attr('stroke-opacity', 0.5)
      .selectAll('line').data(links).join('line').attr('stroke-width', 0.8);

    const sim = this.sim = d3.forceSimulation(nodes)
      // Parent→child bonds. Distance scales with the PARENT's child count so a
      // hub with many children gets a wide enough radius to fan them into a ring
      // instead of a dense ball (circumference must fit all the siblings).
      .force('link', d3.forceLink(links).id(d => d.id).strength(0.9)
        .distance(l => {
          const c = kids[l.source.id || l.source] || 1;
          return Math.max(34, (c * 26) / (2 * Math.PI)) + this._sizeVal(l.target || {});
        }))
      // Repulsion pushes siblings apart tangentially so they spread around the arc.
      .force('charge', d3.forceManyBody().strength(-55).distanceMax(900).theta(0.85))
      .force('collide', d3.forceCollide().radius(d => this._sizeVal(d) + 4).iterations(3))
      .force('center', d3.forceCenter(cx, cy).strength(0.05));
    // Pin home at the centre so the diagram reads "home → sections → pages".
    const rootNode = byId.get(rootId);
    if (rootNode) { rootNode.fx = cx; rootNode.fy = cy; }

    const node = g.append('g').selectAll('circle').data(nodes).join('circle')
      .attr('r', d => this._sizeVal(d))
      .attr('fill', d => this._color(d))
      .attr('stroke', d => this._stroke(d)).attr('stroke-width', d => (d.canonicalized || d.orphan) ? 2 : 1.2)
      .style('cursor', 'pointer')
      .call(this._drag(sim))
      .on('mouseover', (ev, d) => { this._hover(d, node, link); this._showTip(ev, d); })
      .on('mousemove', ev => this._moveTip(ev))
      .on('mouseout', () => { this._unhover(node, link); this.tip.style.display = 'none'; })
      .on('click', (ev, d) => { ev.stopPropagation(); this.onNodeClick(d.id); });

    this._node = node; this._link = link; this._adj = this._adjacency(links);
    this._baseLinkOp = 0.5; this._searchSel = node; this._searchId = d => d.id;

    const ticked = () => {
      link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
      node.attr('cx', d => d.x).attr('cy', d => d.y);
    };
    sim.on('tick', ticked);
    // Pre-warm so it opens already unfolded rather than exploding on screen.
    sim.alpha(1); for (let i = 0; i < 320; i++) sim.tick();
    ticked();
    this._fitToView(svg, g, zoomB, W, H);
    sim.alphaDecay(0.045).alpha(0.15).restart();

    this._legend();
    this._applySearch();
  }

  // ---- 3D crawl diagram (three.js via 3d-force-graph) ----
  async _force3d() {
    this._msg('<span class="sg-spin3d"></span> Loading 3D engine…');
    const mod = await import('3d-force-graph');
    const ForceGraph3D = mod.default;
    if (this.layout !== 'force3d') return;   // user switched away while loading
    this.stage.innerHTML = '';
    // Same URL-path architecture as the 2D tree — root = home, then sections,
    // then posts/pages — laid out top-down in 3D so the hierarchy reads as
    // branches descending from the home node (NOT the crawler's click path).
    const { nodes, links, rootId } = this._dirGraph();
    const dark = matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
    const bg = getComputedStyle(this.container).getPropertyValue('--bg-body').trim() || (dark ? '#0b1220' : '#0f172a');
    const FOLDER = '#64748b';

    const Graph = ForceGraph3D()(this.stage)
      .width(this.stage.clientWidth || 900).height(this.stage.clientHeight || 560)
      .backgroundColor(bg || '#0b1220')
      .graphData({ nodes, links })
      .nodeId('id')
      .dagMode('td')                 // top-down tree: root above, leaves below
      .dagLevelDistance(64)
      .nodeRelSize(5)
      .nodeVal(d => d.node ? Math.max(1, this._sizeVal(d.node) / 3) : (d.id === rootId ? 6 : 2))
      .nodeColor(d => d.node ? this._color(d.node) : (d.id === rootId ? '#2563eb' : FOLDER))
      .nodeOpacity(0.95)
      .nodeLabel(d => {
        const p = pathOf(d.id);
        if (!d.node) return `<div style="font:12px system-ui;padding:4px 6px;background:#111827cc;border-radius:6px;color:#fff">
          <b>${d.id === rootId ? 'Home' : '/' + esc(d.name)}</b><br><span style="opacity:.7">section · ${d.leaves ?? 0} pages</span></div>`;
        return `<div style="font:12px system-ui;padding:4px 6px;background:#111827cc;border-radius:6px;color:#fff">
          <b>${esc((d.node.title || '').slice(0, 60) || p)}</b><br><span style="opacity:.7">${esc(p)}</span><br>
          depth ${esc(d.node.depth ?? ' - ')} · authority ${esc(d.node.pagerank ?? ' - ')} · ${d.node.indexable ? 'indexable' : 'not indexable'}</div>`;
      })
      .linkColor(() => '#8a93a5')
      .linkOpacity(0.35)
      .linkWidth(0.7)
      .linkDirectionalArrowLength(2.6)
      .linkDirectionalArrowRelPos(1)
      .onNodeClick(d => { if (d.node) this.onNodeClick(d.node.id); })
      .enableNodeDrag(true);
    // A DAG tree needs little charge; the level constraint does the spacing.
    Graph.d3Force('charge').strength(-70);
    Graph.cooldownTicks(200);
    Graph.onEngineStop(() => Graph.zoomToFit(700, 60));
    this._graph3d = Graph;
    this._searchSel = null; this._searchId = null;
    this._legend();
  }

  /** Scale + centre a layout's <g> so its whole bounding box fits the stage. */
  _fitToView(svg, g, zoomB, W, H, maxScale = 1.4) {
    let b; try { b = g.node().getBBox(); } catch { return; }
    if (!b || !b.width || !b.height) return;
    const pad = 34;
    const scale = Math.min(W / (b.width + pad * 2), H / (b.height + pad * 2), maxScale);
    const tx = W / 2 - scale * (b.x + b.width / 2);
    const ty = H / 2 - scale * (b.y + b.height / 2);
    svg.call(zoomB.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }

  _adjacency(links) { const a = {}; links.forEach(l => { const s = l.source.id || l.source, t = l.target.id || l.target; (a[s] = a[s] || new Set()).add(t); (a[t] = a[t] || new Set()).add(s); }); return a; }
  _hover(d, node, link) {
    const nb = this._adj[d.id] || new Set();
    node.attr('opacity', o => (o.id === d.id || nb.has(o.id)) ? 1 : 0.1);
    link.attr('stroke-opacity', l => (l.source.id === d.id || l.target.id === d.id) ? 0.95 : 0.03)
        .attr('stroke', l => (l.source.id === d.id || l.target.id === d.id) ? (l.broken ? RED : '#2563eb') : '#94a3b8');
  }
  _unhover(node, link) { node.attr('opacity', 1); link.attr('stroke-opacity', this._baseLinkOp ?? 0.4).attr('stroke', l => l.broken ? RED : '#94a3b8'); this._applySearch(); }
  _recolor() { if (this._node) this._node.attr('fill', d => d.isDir ? 'var(--bg-surface)' : this._color(d)); }
  _applySearch() {
    const sel = this._searchSel; if (!sel) return;
    const q = this.query;
    const idOf = this._searchId || (d => d.id || '');
    sel.attr('opacity', d => { const id = idOf(d); return !q ? 1 : (id && id.toLowerCase().includes(q) ? 1 : 0.1); });
    if (this.layout === 'force' || this.layout === 'arch') {
      const hit = d => q && idOf(d).toLowerCase().includes(q);
      sel.attr('stroke', d => d.id === this._rootId ? 'var(--accent)' : (hit(d) ? '#2563eb' : (d.isDir ? '#94a3b8' : this._stroke(d))))
        .attr('stroke-width', d => d.id === this._rootId ? 3 : (hit(d) ? 3 : (d.isDir ? 2 : ((d.canonicalized || d.orphan) ? 2 : 1.2))));
    }
  }
  _drag(sim) {
    return d3.drag()
      .on('start', (ev, d) => { if (!ev.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag', (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
      .on('end', (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; });
  }
  _showTip(ev, d) {
    const rows = [
      ['Path', pathOf(d.id)], ['Status', d.status ?? ' - '], ['Depth', d.depth ?? ' - '],
      ['Inlinks / Outlinks', `${d.inlinks ?? 0} / ${d.outlinks ?? 0}`],
      ['Authority', d.pagerank == null ? ' - ' : `${d.pagerank}/100`], ['Words', d.words ?? ' - '],
      ['Indexable', d.indexable ? 'Yes' : 'No'],
    ];
    if (d.canonicalized) rows.push(['Canonical', 'points elsewhere']);
    if (d.orphan) rows.push(['⚠ Orphan', '0 inlinks']);
    if (d.issues) rows.push(['Issues', `${d.issues} (worst: ${d.severity})`]);
    this.tip.innerHTML = `<div class="sg-tip-h mono">${d.title ? esc(d.title) + '<br>' : ''}<span class="sg-tip-url">${esc(d.id)}</span></div>` +
      rows.map(([k, v]) => `<div class="sg-tip-r"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
    this.tip.style.display = 'block'; this._moveTip(ev);
  }
  _moveTip(ev) {
    const r = this.container.getBoundingClientRect();
    let x = ev.clientX - r.left + 14, y = ev.clientY - r.top + 14;
    const tw = this.tip.offsetWidth || 260, th = this.tip.offsetHeight || 160;
    if (x + tw > r.width) x = ev.clientX - r.left - tw - 14;
    if (y + th > r.height) y = r.height - th - 8;
    this.tip.style.left = x + 'px'; this.tip.style.top = Math.max(4, y) + 'px';
  }

  // ---- content clusters: circle-packing of the directory hierarchy ----
  _clusters() {
    const W = this.stage.clientWidth || 900, H = this.stage.clientHeight || 560;
    const size = Math.max(200, Math.min(W, H) - 12);
    const rootH = this._dirHierarchy();
    rootH.sum(d => d.node ? this._packVal(d.node) : 0).sort((a, b) => (b.value || 0) - (a.value || 0));
    d3.pack().size([size, size]).padding(d => (d.depth === 0 ? 8 : d.depth === 1 ? 6 : 3))(rootH);

    const sections = (rootH.children || []).map(c => c.data.name);
    this._catScale = d3.scaleOrdinal(sections.length ? sections : ['(root)'], d3.schemeTableau10);
    const sectionOf = (d) => { let a = d; while (a.depth > 1) a = a.parent; return a.depth >= 1 ? a.data.name : '(root)'; };

    const zoomB = d3.zoom().scaleExtent([0.2, 8]).on('zoom', ev => g.attr('transform', ev.transform));
    const svg = d3.select(this.stage).append('svg').attr('width', W).attr('height', H).call(zoomB);
    const g = svg.append('g').attr('transform', `translate(${(W - size) / 2},${(H - size) / 2})`);

    const all = rootH.descendants().filter(d => d.depth > 0);
    const gn = g.selectAll('g').data(all).join('g').attr('transform', d => `translate(${d.x},${d.y})`);
    gn.append('circle')
      .attr('r', d => d.r)
      .attr('fill', d => this._catScale(sectionOf(d)))
      .attr('fill-opacity', d => d.children ? (d.depth === 1 ? 0.09 : 0.05) : 0.88)
      .attr('stroke', d => d.children ? this._catScale(sectionOf(d)) : (d.data.node ? this._stroke(d.data.node) : '#fff'))
      .attr('stroke-opacity', d => d.children ? 0.55 : 1)
      .attr('stroke-width', d => d.children ? 1.2 : 1)
      .style('cursor', d => d.data.node ? 'pointer' : 'default')
      .on('mouseover', (ev, d) => { if (d.data.node) this._showTip(ev, d.data.node); })
      .on('mousemove', ev => this._moveTip(ev))
      .on('mouseout', () => { this.tip.style.display = 'none'; })
      .on('click', (ev, d) => { if (d.data.node) { ev.stopPropagation(); this.onNodeClick(d.data.node.id); } });

    // Section labels on the top-level cluster circles.
    gn.filter(d => d.depth === 1 && d.r > 20).append('text')
      .attr('class', 'sg-cluster-label').attr('text-anchor', 'middle').attr('dy', d => -d.r - 5)
      .attr('font-size', '11px').attr('font-weight', 600).attr('fill', 'currentColor')
      .text(d => '/' + d.data.name);

    this._searchSel = gn.selectAll('circle');
    this._searchId = (d) => (d && d.data && d.data.node) ? d.data.node.id : '';
    this._fitToView(svg, g, zoomB, W, H, 1.6);
    this._legend();
    this._applySearch();
  }

  // ---- hierarchies (tree + directory) ----
  _depthHierarchy() {
    const adj = {}; this.data.edges.forEach(e => (adj[e.source] = adj[e.source] || []).push(e.target));
    const byDepth = [...this.data.nodes].sort((a, b) => (a.depth ?? 99) - (b.depth ?? 99));
    const root = byDepth[0]; const parent = { [root.id]: null }; const queue = [root.id];
    while (queue.length) { const u = queue.shift(); (adj[u] || []).forEach(v => { if (!(v in parent)) { parent[v] = u; queue.push(v); } }); }
    this.data.nodes.forEach(n => { if (!(n.id in parent)) parent[n.id] = (n.id === root.id ? null : root.id); });
    const data = this.data.nodes.map(n => ({ id: n.id, parentId: parent[n.id], node: n }));
    return d3.stratify().id(d => d.id).parentId(d => d.parentId)(data);
  }
  _dirHierarchy() {
    let origin = '/'; try { origin = new URL(this.data.nodes[0].id).origin; } catch { /* */ }
    const root = { name: origin.replace(/^https?:\/\//, ''), id: origin, children: [], _m: {} };
    this.data.nodes.forEach(n => {
      let path; try { path = new URL(n.id).pathname; } catch { return; }
      const segs = path.split('/').filter(Boolean); let cur = root, acc = origin;
      if (!segs.length) { root.node = root.node || n; return; } // homepage sits on the root
      segs.forEach(s => { acc += '/' + s; if (!cur._m[s]) { const c = { name: s, id: acc, children: [], _m: {} }; cur._m[s] = c; cur.children.push(c); } cur = cur._m[s]; });
      cur.node = n;
    });
    return d3.hierarchy(root);
  }
  /** Flat {nodes, links, rootId} for the SAME URL-path architecture hierarchy.
   *  Branch nodes with no real page (e.g. an implicit /blog section) are kept as
   *  folder nodes so the 3D tree shows the full architecture, not just crawled
   *  leaves. Used by the 3D architecture layout. */
  _dirGraph() {
    const rootH = this._dirHierarchy();
    const nodes = rootH.descendants().map(d => ({
      id: d.data.id, name: d.data.name, node: d.data.node || null,
      depth: d.depth, isDir: !d.data.node,
      leaves: d.descendants().filter(x => x.data.node).length,  // pages under this branch
    }));
    const links = rootH.links().map(l => ({ source: l.source.data.id, target: l.target.data.id }));
    return { nodes, links, rootId: rootH.data.id };
  }
  _tree(rootH) {
    const nodesArr = rootH.descendants();
    // Fixed per-node spacing → even, generous gaps regardless of page count.
    const rowGap = 32, colGap = 230;
    d3.tree().nodeSize([rowGap, colGap]).separation((a, b) => (a.parent === b.parent ? 1 : 1.5))(rootH);

    let x0 = Infinity, x1 = -Infinity, y1 = 0;
    rootH.each(d => { if (d.x < x0) x0 = d.x; if (d.x > x1) x1 = d.x; if (d.y > y1) y1 = d.y; });
    const W = Math.max(this.stage.clientWidth || 900, y1 + 340);
    const H = Math.max(this.stage.clientHeight || 560, (x1 - x0) + 80);

    const zoomB = d3.zoom().scaleExtent([0.15, 4]).on('zoom', ev => g.attr('transform', ev.transform));
    const svg = d3.select(this.stage).append('svg').attr('width', W).attr('height', H).call(zoomB);
    const g = svg.append('g').attr('transform', `translate(150,${40 - x0})`);

    // Branches taper trunk → twig: links near the root are thicker so the
    // hierarchy reads as a tree (trunk → boughs → branches → leaves).
    g.append('g').attr('fill', 'none').attr('stroke', 'currentColor').attr('stroke-opacity', 0.24)
      .selectAll('path').data(rootH.links()).join('path')
      .attr('stroke-width', d => Math.max(0.8, 3 - (d.target.depth - 1) * 0.55))
      .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x));

    const rad = d => d.depth === 0 ? Math.max(9, this._sizeVal(d.data.node)) : (d.data.node ? Math.max(4, this._sizeVal(d.data.node)) : 5.5);
    const node = g.append('g').selectAll('g').data(nodesArr).join('g')
      .attr('transform', d => `translate(${d.y},${d.x})`);
    node.append('circle').attr('r', rad)
      // Leaf pages are solid (coloured by the metric); structural section/branch
      // nodes with no page of their own are hollow rings so branches vs leaves
      // read at a glance. The home root gets an extra accent ring.
      .attr('fill', d => d.data.node ? this._color(d.data.node) : 'var(--bg-surface)')
      .attr('stroke', d => d.depth === 0 ? 'var(--accent)' : (d.data.node ? this._stroke(d.data.node) : '#94a3b8'))
      .attr('stroke-width', d => d.depth === 0 ? 3 : (d.data.node ? 1.2 : 2))
      .style('cursor', d => d.data.node ? 'pointer' : 'default')
      .on('mouseover', (ev, d) => { if (d.data.node) this._showTip(ev, d.data.node); })
      .on('mousemove', ev => this._moveTip(ev)).on('mouseout', () => this.tip.style.display = 'none')
      .on('click', (ev, d) => { if (d.data.node) { ev.stopPropagation(); this.onNodeClick(d.data.node.id); } });
    node.append('text').attr('class', 'sg-tree-label')
      // Bolder toward the root: home > sections > pages, so the levels are legible.
      .attr('font-weight', d => d.depth === 0 ? 700 : (d.children ? 600 : 400))
      .attr('dy', '0.31em').attr('x', d => (d.children ? -1 : 1) * (rad(d) + 6))
      .attr('text-anchor', d => d.children ? 'end' : 'start')
      .text(d => { const t = d.depth === 0 ? 'Home' : (d.data.name || pathOf(d.data.id || '')); return t.length > 40 ? t.slice(0, 40) + '…' : t; });

    this._searchSel = node.selectAll('circle');
    this._searchId = (d) => (d && d.data && d.data.node) ? d.data.node.id : (d.data.id || '');
    // A tree with many siblings is naturally tall — fit the *width* to a readable
    // scale and top-align, then let the user scroll/pan vertically. (Fitting the
    // whole height would shrink a 100-page level to specks.)
    const vW = this.stage.clientWidth || 900, vH = this.stage.clientHeight || 560;
    const scale = Math.min(1.1, Math.max(0.5, (vW - 90) / (y1 + 260)));
    // Root (home) is at the left, vertically centred among its branches — frame
    // it in the middle so the user starts at the top of the hierarchy.
    svg.call(zoomB.transform, d3.zoomIdentity.translate(60, vH / 2 - scale * rootH.x).scale(scale));
    this._legend();
    this._applySearch();
  }

  _redirects() {
    const chains = this.data.nodes.filter(n => n.redirect);
    if (!chains.length) return this._msg('No redirects found in this crawl. 🎉');
    this.stage.innerHTML = `<div class="sg-redir">${chains.map(n =>
      `<div class="sg-redir-row" role="button" tabindex="0" data-id="${esc(n.id)}"><span class="badge badge-warning">${esc(n.status)}</span><span class="mono">${esc(pathOf(n.id))}</span></div>`).join('')}</div>`;
    this.stage.querySelectorAll('.sg-redir-row').forEach(r => {
      r.addEventListener('click', () => this.onNodeClick(r.dataset.id));
      r.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.onNodeClick(r.dataset.id); } });
    });
    this.container.querySelector('.sg-legend').innerHTML = '';
  }
}
