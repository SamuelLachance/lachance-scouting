const FLAGS = { CAN:'🇨🇦', CDN:'🇨🇦', USA:'🇺🇸', SWE:'🇸🇪', FIN:'🇫🇮', CZE:'🇨🇿', SVK:'🇸🇰', RUS:'🇷🇺', SUI:'🇨🇭', GER:'🇩🇪', LAT:'🇱🇻', BLR:'🇧🇾', KAZ:'🇰🇿', AUT:'🇦🇹', NOR:'🇳🇴' };

const SKILL_KEYS = [
  'starCeiling', 'hockeyIQ', 'skatingEngine', 'offensiveStarPower',
  'competitionProof', 'characterCompete', 'developmentArc',
];

const SKILL_LABELS = {
  starCeiling: 'Plafond étoile NHL ★',
  hockeyIQ: 'IQ / processing élite',
  skatingEngine: 'Moteur de patinage',
  offensiveStarPower: 'Pouvoir offensif star',
  competitionProof: 'Preuve vs compétition',
  characterCompete: 'Compétitivité / caractère',
  developmentArc: 'Arc de développement',
};

const SKILL_WEIGHTS = {
  starCeiling: 35, hockeyIQ: 18, skatingEngine: 15, offensiveStarPower: 12,
  competitionProof: 10, characterCompete: 5, developmentArc: 5,
};

let draftManifest = { defaultYear: 2026, years: [] };
let draftYear = 2026;
let players = [];
let playersCache = {};
let chartInstance = null;
let state = {
  query: '', position: 'ALL', country: 'ALL', tier: 'ALL', minScore: 0, minDiscovery: 0, hiddenOnly: false,
  compareA: '', compareB: '', listPage: 0,
  headerSearch: '', searchHighlight: 0,
};
const PAGE_SIZE = 50;

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
}

function formatRationale(text) {
  if (!text) return '<span style="color:#64748b;font-style:italic">Justification en cours de génération.</span>';
  return esc(text).replace(/\*\*([^*]+)\*\*/g, '<strong style="color:#e2e8f0">$1</strong>');
}

function showError(msg) {
  document.getElementById('app').innerHTML =
    '<div class="glass" style="padding:2rem;text-align:center;margin:2rem;max-width:520px;margin-inline:auto">' +
    '<p style="color:#f87171;margin-bottom:1rem">' + esc(msg) + '</p>' +
    '<p style="color:#94a3b8;font-size:14px">Lancez <code>start.bat</code> puis ouvrez ' +
    '<a href="http://localhost:8080" style="color:var(--ice-400)">http://localhost:8080</a></p></div>';
}

function currentDraftMeta() {
  return (draftManifest.years || []).find(y => y.year === draftYear) || { year: draftYear, status: 'active', label: 'Repêchage ' + draftYear };
}

async function loadManifest() {
  const res = await fetch('./data/drafts.json');
  if (!res.ok) throw new Error('Manifeste repêchages introuvable (data/drafts.json)');
  draftManifest = await res.json();
  if (!draftYear) draftYear = draftManifest.defaultYear || 2026;
}

async function loadPlayersForYear(year) {
  if (playersCache[year]) {
    players = playersCache[year];
    return;
  }
  const meta = (draftManifest.years || []).find(y => y.year === year);
  if (meta && meta.status === 'upcoming') {
    players = [];
    playersCache[year] = [];
    return;
  }
  const res = await fetch('./data/' + year + '/players.json');
  if (!res.ok) throw new Error('Données ' + year + ' introuvables. Exécutez python build_site_data.py');
  players = await res.json();
  players.sort((a, b) => b.overall - a.overall || a.name.localeCompare(b.name));
  playersCache[year] = players;
}

function draftHref(subpath) {
  const p = subpath.startsWith('/') ? subpath : '/' + subpath;
  return '#/' + draftYear + (p === '/' ? '' : p);
}

function normalizeHash() {
  const raw = location.hash.slice(1) || '';
  if (!raw || raw === '/') {
    location.replace('#/' + (draftManifest.defaultYear || 2026));
    return draftManifest.defaultYear || 2026;
  }
  const parts = raw.split('/').filter(Boolean);
  if (parts.length && !/^\d{4}$/.test(parts[0])) {
    location.replace('#/' + (draftManifest.defaultYear || 2026) + '/' + parts.join('/'));
    return draftManifest.defaultYear || 2026;
  }
  return parts.length && /^\d{4}$/.test(parts[0]) ? parseInt(parts[0], 10) : (draftManifest.defaultYear || 2026);
}

async function init() {
  try {
    await loadManifest();
    draftYear = normalizeHash();
    await loadPlayersForYear(draftYear);
    window.addEventListener('hashchange', onHashChange);
    render();
  } catch (e) {
    showError(e.message || String(e));
  }
}

async function onHashChange() {
  const year = normalizeHash();
  if (year !== draftYear) {
    draftYear = year;
    state.listPage = 0;
    state.query = '';
    state.headerSearch = '';
    await loadPlayersForYear(draftYear);
  }
  render();
}

async function switchDraftYear(year) {
  if (year === draftYear) return;
  draftYear = year;
  state.listPage = 0;
  state.query = '';
  state.headerSearch = '';
  location.hash = '/' + year;
}

window.addEventListener('unhandledrejection', function (ev) {
  console.error(ev.reason);
});

function route() {
  const hash = location.hash.slice(1) || '';
  const qIdx = hash.indexOf('?');
  const pathPart = qIdx >= 0 ? hash.slice(0, qIdx) : hash;
  const queryPart = qIdx >= 0 ? hash.slice(qIdx + 1) : '';
  const parts = pathPart.split('/').filter(Boolean);
  let year = draftYear;
  let rest = parts;
  if (parts.length && /^\d{4}$/.test(parts[0])) {
    year = parseInt(parts[0], 10);
    rest = parts.slice(1);
  }
  if (rest[0] === 'player') return { page: 'player', year, id: rest[1] };
  if (rest[0] === 'compare') {
    const q = new URLSearchParams(queryPart);
    return { page: 'compare', year, a: q.get('a') || '', b: q.get('b') || '' };
  }
  return { page: 'home', year };
}

function scoreClass(s) {
  if (s >= 90) return 'score-elite';
  if (s >= 75) return 'score-high';
  if (s >= 60) return 'score-mid';
  return 'score-low';
}

function posBadge(p) {
  const u = p.toUpperCase();
  if (u === 'G') return 'badge-g';
  if (u === 'D' || u.includes('D')) return 'badge-d';
  if (u === 'C') return 'badge-c';
  return 'badge-f';
}

function tierClass(t) {
  const s = (t || '').toLowerCase();
  if (s.includes('génération') || s.includes('generational')) return 'tier-generational';
  if (s.includes('franchise')) return 'tier-franchise';
  if (s.includes('élite') || s.includes('elite')) return 'tier-elite';
  if (s.includes('premier trio') || s.includes('première paire') || s.includes('top-line') || s.includes('top-pair')) return 'tier-top';
  if (s.includes('top 6') || s.includes('top 4') || s.includes('top six') || s === 'titulaire') return 'tier-top';
  if (s.includes('top 9') || s.includes('7e') || s.includes('partiel') || s.includes('troisième trio') || s.includes('troisième paire')) return 'tier-mid';
  if (s.includes('quatrième') || s.includes('remplaçant') || s.includes('lha')) return 'tier-depth';
  return 'tier-low';
}

function deltaBadge(d) {
  if (d == null || d === 0) return '';
  const cls = d > 0 ? 'color:#34d399' : 'color:#fb7185';
  const arrow = d > 0 ? '↑' : '↓';
  return `<span style="font-size:11px;font-family:var(--font-mono);${cls}">${arrow}${Math.abs(d)}</span>`;
}

function rankClass(r) {
  if (r <= 10) return 'rank-gold';
  if (r <= 32) return 'rank-ice';
  return 'rank-dim';
}

function barClass(v) {
  if (v >= 9) return 'bar-elite';
  if (v >= 7.5) return 'bar-high';
  if (v >= 6) return 'bar-mid';
  return 'bar-low';
}

function discoveryClass(s) {
  if (s >= 85) return 'discovery-alert';
  if (s >= 75) return 'discovery-diamond';
  if (s >= 65) return 'discovery-watch';
  if (s >= 55) return 'discovery-latent';
  return 'discovery-market';
}

function discoverySignal(p) {
  if (p.discoverySignal) return p.discoverySignal;
  const sk = p.skills || {};
  const baseScore = p.baseNorthstarScore || p.overall;
  const upsideCore =
    (sk.starCeiling || 5) * 3 +
    (sk.hockeyIQ || 5) * 1.8 +
    (sk.skatingEngine || 5) * 1.6 +
    (sk.offensiveStarPower || 5) * 1.6 +
    (sk.developmentArc || 5) * 1.2 +
    (sk.competitionProof || 5) * 0.8;
  const marketGap = p.consensusRank ? p.consensusRank - p.rank : null;
  const marketBoost = marketGap == null ? 8 : Math.max(-10, Math.min(22, marketGap * 0.45));
  const rareToolCount = Object.values(sk).filter(v => v >= 8.5).length;
  const score = Math.max(0, Math.min(99, baseScore * 0.62 + upsideCore * 0.38 + marketBoost + rareToolCount * 2));
  return {
    score: Number(score.toFixed(1)),
    label: score >= 75 ? 'Diamant sous-évalué' : score >= 65 ? 'Upside à surveiller' : 'Signal latent',
    marketGap,
    marketStatus: marketGap == null ? 'Aucun consensus public fiable' : marketGap > 0 ? `Consensus ${marketGap} rangs plus bas que NORTHSTAR` : marketGap < 0 ? `Consensus ${Math.abs(marketGap)} rangs plus haut que NORTHSTAR` : 'Consensus aligné avec NORTHSTAR',
    upsideCore: Number(upsideCore.toFixed(1)),
    rareToolCount,
    peakTool: { label: 'profil', score: Math.max(...Object.values(sk).map(Number)) || 0 },
    confidenceLabel: 'Confiance moyenne',
    reasons: ['Signal généré côté interface en attente des données Discovery.'],
  };
}

function discoveryPill(d) {
  return `<span class="discovery-pill ${discoveryClass(d.score)}" title="${esc(d.marketStatus || d.label)}"><strong>${d.score.toFixed(1)}</strong><small>${esc(d.label)}</small></span>`;
}

function isHiddenOpportunity(p) {
  const d = discoverySignal(p);
  return d.score >= 65 && (d.marketGap == null || d.marketGap >= 8);
}

function normalizeName(s) {
  return String(s).normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
}

function matchPlayersByName(q, limit) {
  limit = limit || 10;
  const nq = normalizeName(q.trim());
  if (!nq) return [];
  return players
    .map(p => {
      const name = normalizeName(p.name);
      const parts = name.split(/\s+/);
      let score = 0;
      if (name === nq) score = 100;
      else if (name.startsWith(nq)) score = 85;
      else if (parts.some(part => part.startsWith(nq))) score = 75;
      else if (parts.some(part => part.includes(nq))) score = 60;
      else if (name.includes(nq)) score = 45;
      else return null;
      return { p, score };
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score || a.p.rank - b.p.rank)
    .slice(0, limit)
    .map(x => x.p);
}

function filterPlayers() {
  const q = normalizeName(state.query);
  return players.filter(p => {
    const d = discoverySignal(p);
    if (q && !normalizeName(p.name).includes(q)) return false;
    if (state.position !== 'ALL' && p.position !== state.position) return false;
    if (state.country !== 'ALL' && p.country !== state.country) return false;
    if (state.tier !== 'ALL' && p.tier !== state.tier) return false;
    if (p.overall < state.minScore) return false;
    if (d.score < state.minDiscovery) return false;
    if (state.hiddenOnly && !isHiddenOpportunity(p)) return false;
    return true;
  }).sort((a, b) => b.overall - a.overall || a.name.localeCompare(b.name));
}

function getStats() {
  if (!players.length) {
    return { total: 0, generational: 0, franchise: 0, elite: 0, avg: '0.0', avgDiscovery: '0.0', hiddenStars: 0, countries: 0 };
  }
  return {
    total: players.length,
    generational: players.filter(p => tierClass(p.tier) === 'tier-generational').length,
    franchise: players.filter(p => tierClass(p.tier) === 'tier-franchise').length,
    elite: players.filter(p => tierClass(p.tier) === 'tier-elite').length,
    avg: (players.reduce((s,p) => s + p.overall, 0) / players.length).toFixed(1),
    avgDiscovery: (players.reduce((s,p) => s + discoverySignal(p).score, 0) / players.length).toFixed(1),
    hiddenStars: players.filter(p => discoverySignal(p).score >= 75 && isHiddenOpportunity(p)).length,
    countries: new Set(players.map(p => p.country)).size
  };
}

function yearSelector() {
  const years = (draftManifest.years || []).slice().sort((a, b) => b.year - a.year);
  return `<div class="year-select-wrap">
    <label for="draft-year" class="year-select-label">Repêchage</label>
    <select id="draft-year" class="year-select" aria-label="Choisir le repêchage">
      ${years.map(y => `<option value="${y.year}" ${y.year === draftYear ? 'selected' : ''} ${y.status === 'upcoming' ? '' : ''}>${y.year}${y.status === 'upcoming' ? ' · bientôt' : y.status === 'active' ? ' · actif' : ''}</option>`).join('')}
    </select>
  </div>`;
}

function header(active) {
  const meta = currentDraftMeta();
  return `<header><div class="header-inner">
    <a href="${draftHref('')}" class="logo">
      <div class="logo-icon"><svg width="20" height="20" fill="white" viewBox="0 0 24 24"><path d="M12 2L15 8.5L22 9.3L17 14L18.5 21L12 17.8L5.5 21L7 14L2 9.3L9 8.5Z"/></svg></div>
      <div><h1>Lachance Scouting</h1><p>${meta.label || ('NHL ' + draftYear)} · NORTHSTAR</p></div>
    </a>
    ${yearSelector()}
    <div class="global-search" id="global-search-wrap">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input type="search" id="global-search" placeholder="Rechercher un joueur…" autocomplete="off"
        value="${esc(state.headerSearch)}" aria-label="Rechercher un joueur par nom" />
      <div class="search-dropdown" id="search-dropdown"></div>
    </div>
    <nav>
      <a href="${draftHref('')}" class="${active === 'home' ? 'active' : ''}">Classement</a>
      <a href="${draftHref('/compare')}" class="${active === 'compare' ? 'active' : ''}">Comparer</a>
    </nav>
  </div></header>`;
}

function footer() {
  return `<footer>Lachance Scouting · Repêchage ${draftYear} · ${players.length} prospects</footer>`;
}

function renderUpcoming() {
  const meta = currentDraftMeta();
  return `${header('home')}<main class="fade-in">
    <h2 class="page-title">${esc(meta.label || ('Repêchage ' + draftYear))}</h2>
    <p class="page-sub">${esc(meta.subtitle || 'À venir')}</p>
    <div class="glass" style="padding:3rem 2rem;text-align:center;max-width:520px;margin:2rem auto">
      <p style="font-size:2.5rem;margin-bottom:1rem">🏒</p>
      <p style="color:#94a3b8;margin-bottom:1.5rem">Ce repêchage sera ajouté à Lachance Scouting une fois la classe éligible disponible.</p>
      <a href="${draftHref('')}" class="btn-primary" onclick="switchDraftYear(${draftManifest.defaultYear || 2026});return false;">Voir le repêchage ${draftManifest.defaultYear || 2026}</a>
    </div>
  </main>${footer()}`;
}

function renderHome() {
  const filtered = filterPlayers();
  const stats = getStats();
  const positions = [...new Set(players.map(p => p.position))].sort();
  const countries = [...new Set(players.map(p => p.country))].sort();
  const tiers = [...new Set(players.map(p => p.tier))];

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  if (state.listPage >= totalPages) state.listPage = totalPages - 1;
  if (state.listPage < 0) state.listPage = 0;
  const pageItems = filtered.slice(state.listPage * PAGE_SIZE, (state.listPage + 1) * PAGE_SIZE);

  const pagination = filtered.length > PAGE_SIZE ? `
    <div class="pagination">
      <button id="pg-prev" ${state.listPage === 0 ? 'disabled' : ''}>← Précédent</button>
      <span>Page ${state.listPage + 1} / ${totalPages} · ${filtered.length} joueurs</span>
      <button id="pg-next" ${state.listPage >= totalPages - 1 ? 'disabled' : ''}>Suivant →</button>
    </div>` : '';

  return `${header('home')}<main class="fade-in">
    <h2 class="page-title">Classement NORTHSTAR Discovery · ${draftYear}</h2>
    <p class="page-sub">NORTHSTAR Discovery Rating — tous les prospects reclassés pour détecter les futures étoiles avant le consensus public</p>

    <div class="stats-grid">
      <div class="glass stat-card"><div class="stat-label">Prospects</div><div class="stat-value" style="color:var(--ice-400)">${stats.total}</div></div>
      <div class="glass stat-card"><div class="stat-label">Diamants</div><div class="stat-value" style="color:#f0abfc">${stats.hiddenStars}</div></div>
      <div class="glass stat-card"><div class="stat-label">Franchise</div><div class="stat-value" style="color:var(--gold)">${stats.franchise}</div></div>
      <div class="glass stat-card"><div class="stat-label">Élite</div><div class="stat-value" style="color:#34d399">${stats.elite}</div></div>
      <div class="glass stat-card"><div class="stat-label">Pays</div><div class="stat-value" style="color:#a78bfa">${stats.countries}</div></div>
      <div class="glass stat-card"><div class="stat-label">NDR moyen</div><div class="stat-value" style="color:var(--ice-400)">${stats.avg}</div></div>
      <div class="glass stat-card"><div class="stat-label">Discovery moy.</div><div class="stat-value" style="color:#34d399">${stats.avgDiscovery}</div></div>
    </div>

    <div class="glass filters">
      <div class="filters-row">
        <select id="f-pos"><option value="ALL">Toutes positions</option>${positions.map(p => `<option value="${p}" ${state.position===p?'selected':''}>${p}</option>`).join('')}</select>
        <select id="f-country"><option value="ALL">Tous pays</option>${countries.map(c => `<option value="${c}" ${state.country===c?'selected':''}>${FLAGS[c]||''} ${c}</option>`).join('')}</select>
        <select id="f-tier"><option value="ALL">Tous tiers</option>${tiers.map(t => `<option value="${t}" ${state.tier===t?'selected':''}>${t}</option>`).join('')}</select>
        <div style="flex:1;min-width:140px">
          <label style="font-size:10px;color:#64748b;text-transform:uppercase">NDR min: <span id="min-label">${state.minScore}</span></label>
          <input type="range" id="f-min" min="0" max="95" step="5" value="${state.minScore}" style="width:100%;accent-color:var(--ice-500)" />
        </div>
        <div style="flex:1;min-width:150px">
          <label style="font-size:10px;color:#64748b;text-transform:uppercase">Discovery min: <span id="discovery-label">${state.minDiscovery}</span></label>
          <input type="range" id="f-discovery" min="0" max="95" step="5" value="${state.minDiscovery}" style="width:100%;accent-color:#e879f9" />
        </div>
        <label class="toggle-filter">
          <input type="checkbox" id="f-hidden" ${state.hiddenOnly ? 'checked' : ''} />
          Marché inefficace
        </label>
      </div>
      <div class="filter-meta"><span>Filtres actifs${state.query ? ' · nom: « ' + esc(state.query) + ' »' : ''}</span><span>${filtered.length} résultats</span></div>
    </div>

    <div class="glass" style="overflow:hidden">
      <table>
        <thead><tr>
          <th>#</th><th>Joueur</th><th class="hidden-sm">Pos</th><th class="hidden-md">Taille</th>
          <th class="hidden-md">Pays</th><th class="hidden-sm">Projection</th>
          <th class="hidden-md">Signal caché</th><th style="text-align:right">NDR</th>
        </tr></thead>
        <tbody>${pageItems.map(p => `
          <tr onclick="location.hash='/${draftYear}/player/${p.id}'">
            <td><span class="${rankClass(p.rank)}">${p.rank}</span></td>
            <td><strong>${esc(p.name)}</strong><div class="hidden-sm" style="font-size:11px;color:#64748b">${p.position} · ${p.height}</div></td>
            <td class="hidden-sm"><span class="badge ${posBadge(p.position)}">${p.position}</span></td>
            <td class="hidden-md" style="font-family:var(--font-mono);font-size:12px;color:#94a3b8">${p.height} / ${p.weight}</td>
            <td class="hidden-md">${FLAGS[p.country]||'🏳️'} ${p.country}</td>
            <td class="hidden-sm"><span class="tier projection-cell ${tierClass(p.tier)}" title="${esc(p.eaTier || p.tier)}">${esc(p.projection || p.tier)}</span></td>
            <td class="hidden-md">${discoveryPill(discoverySignal(p))}</td>
            <td style="text-align:right"><span class="${scoreClass(p.overall)}">${p.overall.toFixed(1)}</span></td>
          </tr>`).join('')}
        </tbody>
      </table>
      ${filtered.length === 0 ? '<div style="padding:3rem;text-align:center;color:#64748b">Aucun joueur ne correspond aux filtres.</div>' : ''}
      ${pagination}
    </div>
  </main>${footer()}`;
}

function portraitHtml(p) {
  const url = p.photoUrl || `./images/players/${p.draftYear || draftYear}/${p.id}.svg`;
  return `<img class="player-portrait" src="${esc(url)}" alt="Portrait de ${esc(p.name)}" loading="lazy" referrerpolicy="no-referrer" />`;
}

function renderPlayer(id) {
  const p = players.find(x => x.id === id);
  if (!p) return `${header('home')}<main><div class="glass" style="padding:3rem;text-align:center"><p style="color:#94a3b8;margin-bottom:1rem">Joueur introuvable.</p><a href="${draftHref('')}" class="btn-primary">Retour</a></div></main>${footer()}`;

  const prev = players.find(x => x.rank === p.rank - 1);
  const next = players.find(x => x.rank === p.rank + 1);
  const a = p.analysis;
  const pct = `${p.overall}%`;
  const d = discoverySignal(p);

  const rationales = p.skillRationales || {};
  const skillBars = SKILL_KEYS.map(key => {
    const label = SKILL_LABELS[key];
    const v = p.skills[key];
    const w = SKILL_WEIGHTS[key];
    const why = rationales[key] || '';
    return `<div class="skill-block">
      <div class="skill-bar">
        <div class="skill-bar-header"><span>${label}</span><span>${v.toFixed(1)} <span style="color:#475569">(${w}% → ${(v*w/10).toFixed(1)})</span></span></div>
        <div class="bar-track"><div class="bar-fill ${barClass(v)}" style="width:${v*10}%"></div></div>
      </div>
      <p class="skill-rationale">${formatRationale(why)}</p>
    </div>`;
  }).join('');

  return `${header('home')}<main class="fade-in">
    <div class="nav-player">
      <a href="${draftHref('')}">← Retour au classement</a>
      <div class="nav-btns">
        ${prev ? `<a href="${draftHref('/player/' + prev.id)}">← #${prev.rank} ${esc(prev.name.split(' ').pop())}</a>` : ''}
        ${next ? `<a href="${draftHref('/player/' + next.id)}">#${next.rank} ${esc(next.name.split(' ').pop())} →</a>` : ''}
      </div>
    </div>

    <div class="glass player-hero">
      <div class="player-header">
        <div class="player-portrait-wrap">
          ${portraitHtml(p)}
        </div>
        <div class="score-ring" style="--pct:${pct}">
          ${p.rank <= 10 ? `<div class="rank-pin">${p.rank}</div>` : ''}
          <div class="score-ring-inner">
            <span class="val ${scoreClass(p.overall)}">${p.overall.toFixed(1)}</span>
            <span class="lbl">/ 100</span>
          </div>
        </div>
        <div>
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px">
            <span class="rank-gold" style="font-size:13px">#${p.rank} NORTHSTAR</span>
            <span style="font-size:12px;color:#64748b;font-family:var(--font-mono)">NDR ${p.overall.toFixed(1)}${p.baseNorthstarScore ? ` · Talent ${Number(p.baseNorthstarScore).toFixed(1)}` : ''}${p.consensusRank ? ` · Cons. #${p.consensusRank}` : ''}</span>
            ${p.isOverAge ? `<span style="font-size:11px;color:#fb7185;font-family:var(--font-mono);padding:2px 8px;border:1px solid rgba(251,113,133,.35);border-radius:6px" title="Éligible 2025, non repêché">Over-age · -${(p.overAgePenalty || 0).toFixed(0)} SPI</span>` : ''}
            <span class="tier ${tierClass(p.tier)}" title="${p.eaTier || p.tier}">${p.tier}</span>
            ${discoveryPill(d)}
          </div>
          <h1 class="player-name">${esc(p.name)}</h1>
          <div class="player-meta">
            <span class="badge ${posBadge(p.position)}">${p.position}</span>
            <span>${p.height} · ${p.weight} lbs · Tire ${p.shoots}</span>
            <span>${FLAGS[p.country]||'🏳️'} ${p.country}</span>
          </div>
          ${a.resume ? `<p class="player-resume">${esc(a.resume)}</p>` : ''}
          ${a.upsideThesis ? `<p class="player-resume" style="margin-top:8px;border-left:3px solid var(--gold);padding-left:12px;color:#cbd5e1"><strong style="color:var(--gold);font-size:11px;text-transform:uppercase">Thèse upside</strong><br>${esc(a.upsideThesis)}</p>` : ''}
        </div>
      </div>
    </div>

    <div class="glass card discovery-card">
      <div class="discovery-score ${discoveryClass(d.score)}">
        <strong>${d.score.toFixed(1)}</strong>
        <span>Discovery</span>
      </div>
      <div class="discovery-main">
        <h3>${esc(d.label)}</h3>
        <p>${esc(d.marketStatus || '')}</p>
        <div class="discovery-metrics">
          <span><small>Upside pur</small>${Number(d.upsideCore || 0).toFixed(1)}/100</span>
          <span><small>Outil signature</small>${esc((d.peakTool && d.peakTool.label) || 'profil')} ${Number((d.peakTool && d.peakTool.score) || 0).toFixed(1)}</span>
          <span><small>Confiance</small>${esc(d.confidenceLabel || 'Confiance moyenne')}</span>
        </div>
        <div class="discovery-reasons">
          ${(d.reasons || []).map(r => `<span>${esc(r)}</span>`).join('')}
        </div>
      </div>
    </div>

    <div class="glass card" style="margin-top:0">
      <h3>Grille NORTHSTAR — notes et justifications</h3>
      <p style="font-size:13px;color:#64748b;margin:-4px 0 1.25rem">Chaque dimension explique pourquoi cette note /10 a été attribuée dans le modèle upside.</p>
      ${skillBars}
      <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid rgba(255,255,255,.06)">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="color:#64748b;font-size:14px">NORTHSTAR Discovery Rating</span>
          <span class="${scoreClass(p.overall)}" style="font-size:1.75rem">${p.overall.toFixed(1)}/100</span>
        </div>
        ${p.isOverAge ? `<p style="margin:10px 0 0;font-size:13px;color:#fb7185">Pénalité over-age : -${(p.overAgePenalty || 0).toFixed(1)} SPI${p.spiBeforePenalty != null ? ` (avant pénalité : ${Number(p.spiBeforePenalty).toFixed(1)})` : ''}</p>` : ''}
      </div>
    </div>

    <div class="analysis-grid">
      <div class="glass analysis-card positive"><h3>Forces</h3><ul>${(a.forces||[]).map(f=>`<li>${esc(f)}</li>`).join('')||'<li>—</li>'}</ul></div>
      <div class="glass analysis-card negative"><h3>Faiblesses / Risques</h3><ul>${(a.faiblesses||[]).map(f=>`<li>${esc(f)}</li>`).join('')||'<li>—</li>'}</ul></div>
    </div>

    <div class="grid-2">
      <div class="glass card"><h3 style="font-size:11px;text-transform:uppercase;color:#64748b;font-weight:400;margin-bottom:8px">Comparable NHL</h3><p>${esc(a.comparable||'—')}</p></div>
      <div class="glass card"><h3 style="font-size:11px;text-transform:uppercase;color:#64748b;font-weight:400;margin-bottom:8px">Projection</h3><p>${esc(p.projection || a.projection || p.tier || '—')}</p></div>
    </div>

    <div style="text-align:center;margin-top:1.5rem">
      <a href="${draftHref('/compare?a=' + p.id)}" class="btn-primary">Comparer avec un autre prospect →</a>
    </div>
  </main>${footer()}`;
}

function renderCompare(aId, bId) {
  const a = aId ? players.find(p => p.id === aId) : null;
  const b = bId ? players.find(p => p.id === bId) : null;
  const top32 = players.filter(p => p.rank <= 32);
  const meta = currentDraftMeta();

  const opts = players.map(p =>
    `<option value="${p.id}">#${p.rank} ${esc(p.name)} (${p.overall.toFixed(1)} · D ${discoverySignal(p).score.toFixed(1)})</option>`
  ).join('');

  let compareSection = '<div class="glass card" style="padding:2rem;text-align:center;color:#64748b">Sélectionnez deux joueurs pour comparer.</div>';
  if (meta.status === 'upcoming' || !players.length) {
    compareSection = '<div class="glass card" style="padding:2rem;text-align:center;color:#64748b">Les données de ce repêchage ne sont pas encore disponibles.</div>';
  } else if ((aId && !a) || (bId && !b)) {
    compareSection = '<div class="glass card" style="padding:2rem;text-align:center;color:#64748b">Un ou plusieurs joueurs sont introuvables pour ce repêchage.</div>';
  } else if (a && b) {
    const da = discoverySignal(a);
    const db = discoverySignal(b);
    const rows = Object.entries(SKILL_LABELS).map(([k,l]) => {
      const va = a.skills[k], vb = b.skills[k], d = va - vb;
      return `<tr><td style="color:#94a3b8">${l}</td><td style="font-family:var(--font-mono)">${va.toFixed(1)}</td><td style="font-family:var(--font-mono)">${vb.toFixed(1)}</td><td style="text-align:right;font-family:var(--font-mono);color:${d>0?'#34d399':d<0?'#fb7185':'#64748b'}">${d>0?'+':''}${d.toFixed(1)}</td></tr>`;
    }).join('');

    compareSection = `
      <div class="glass card"><canvas id="radar"></canvas>
        <div style="display:flex;justify-content:center;gap:2rem;margin-top:8px;font-size:13px">
          <span><span style="display:inline-block;width:12px;height:12px;background:var(--ice-500);border-radius:50%;margin-right:6px"></span>${esc(a.name)} (${a.overall.toFixed(1)})</span>
          <span><span style="display:inline-block;width:12px;height:12px;background:var(--gold);border-radius:50%;margin-right:6px"></span>${esc(b.name)} (${b.overall.toFixed(1)})</span>
        </div>
      </div>
      <div class="glass" style="overflow:hidden;margin-top:1rem">
        <table><thead><tr><th>Métrique</th><th>${esc(a.name)}</th><th>${esc(b.name)}</th><th style="text-align:right">Δ A−B</th></tr></thead>
        <tbody>
          <tr><td style="color:#94a3b8">Rang NORTHSTAR</td><td>#${a.rank}</td><td>#${b.rank}</td><td style="text-align:right;font-family:var(--font-mono);color:${a.rank<b.rank?'#34d399':'#fb7185'}">${a.rank - b.rank}</td></tr>
          <tr><td style="color:#94a3b8">Tier EA</td><td><span class="tier ${tierClass(a.tier)}" title="${esc(a.eaTier || a.tier)}">${esc(a.tier)}</span></td><td><span class="tier ${tierClass(b.tier)}" title="${esc(b.eaTier || b.tier)}">${esc(b.tier)}</span></td><td></td></tr>
          <tr><td style="color:#94a3b8">Projection</td><td>${esc(a.projection || a.tier || '—')}</td><td>${esc(b.projection || b.tier || '—')}</td><td></td></tr>
          <tr><td style="color:#94a3b8">Consensus</td><td>${a.consensusRank?'#'+a.consensusRank:'—'}</td><td>${b.consensusRank?'#'+b.consensusRank:'—'}</td><td></td></tr>
          <tr><td style="color:#94a3b8">NDR</td><td>${a.overall.toFixed(1)}</td><td>${b.overall.toFixed(1)}</td><td style="text-align:right;font-family:var(--font-mono);color:${a.overall>b.overall?'#34d399':'#fb7185'}">${(a.overall-b.overall).toFixed(1)}</td></tr>
          <tr><td style="color:#94a3b8">Discovery</td><td>${discoveryPill(da)}</td><td>${discoveryPill(db)}</td><td style="text-align:right;font-family:var(--font-mono);color:${da.score>db.score?'#34d399':'#fb7185'}">${(da.score-db.score).toFixed(1)}</td></tr>
          ${rows}
        </tbody></table>
      </div>`;
  }

  return `${header('compare')}<main class="fade-in">
    <h2 class="page-title">Comparateur de prospects</h2>
    <p class="page-sub">Superposez les profils radar pour évaluer deux options de repêchage</p>

    <div class="compare-selects">
      <div class="glass card"><label style="font-size:11px;color:#64748b;text-transform:uppercase;display:block;margin-bottom:8px">Joueur A</label>
        <select id="cmp-a" style="width:100%;background:rgba(17,24,39,.8);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px;color:#e2e8f0">
          <option value="">— Choisir —</option>${opts}</select></div>
      <div class="glass card"><label style="font-size:11px;color:#64748b;text-transform:uppercase;display:block;margin-bottom:8px">Joueur B</label>
        <select id="cmp-b" style="width:100%;background:rgba(17,24,39,.8);border:1px solid rgba(255,255,255,.06);border-radius:8px;padding:10px;color:#e2e8f0">
          <option value="">— Choisir —</option>${opts}</select></div>
    </div>

    ${compareSection}

    <div class="glass card" style="margin-top:1.5rem">
      <h3 style="font-size:13px;color:#94a3b8;margin-bottom:12px">Raccourcis — Top 32</h3>
      <div class="chips">${top32.map(p => `<button class="chip" data-id="${p.id}">#${p.rank} ${esc(p.name.split(' ').pop())}</button>`).join('')}</div>
    </div>
  </main>${footer()}`;
}

function drawRadar(skills, compareSkills) {
  const canvas = document.getElementById('radar');
  if (!canvas || !window.Chart) return;
  if (chartInstance) { chartInstance.destroy(); chartInstance = null; }

  const labels = ['Plafond','IQ','Patinage','Offensif','Preuve','Compete','Arc'];
  const keys = SKILL_KEYS;
  const data = keys.map(k => skills[k] ?? 5);

  const datasets = [{
    label: 'Joueur', data, borderColor: '#38bdf8', backgroundColor: 'rgba(14,165,233,.2)',
    borderWidth: 2, pointBackgroundColor: '#38bdf8'
  }];

  if (compareSkills) {
    datasets.push({
      label: 'Compare', data: keys.map(k => compareSkills[k]),
      borderColor: '#fbbf24', backgroundColor: 'rgba(251,191,36,.15)',
      borderWidth: 2, pointBackgroundColor: '#fbbf24'
    });
  }

  chartInstance = new Chart(canvas, {
    type: 'radar',
    data: { labels, datasets },
    options: {
      responsive: true,
      scales: { r: { min: 0, max: 10, ticks: { stepSize: 2, color: '#475569', backdropColor: 'transparent' }, grid: { color: 'rgba(255,255,255,.06)' }, pointLabels: { color: '#94a3b8', font: { size: 11 } } } },
      plugins: { legend: { display: false } }
    }
  });
}

function renderSearchDropdown(matches, highlight) {
  const dropdown = document.getElementById('search-dropdown');
  if (!dropdown) return;
  const q = state.headerSearch.trim();
  if (!q) {
    dropdown.innerHTML = '';
    dropdown.classList.remove('open');
    return;
  }
  if (!matches.length) {
    dropdown.innerHTML = '<div class="search-empty">Aucun joueur pour « ' + esc(q) + ' »</div>';
    dropdown.classList.add('open');
    return;
  }
  dropdown.innerHTML = matches.map((p, i) =>
    '<button type="button" class="search-result' + (i === highlight ? ' active' : '') + '" data-id="' + p.id + '">' +
    '<span class="search-result-rank">#' + p.rank + '</span>' +
    '<span class="search-result-body">' +
    '<span class="search-result-name">' + esc(p.name) + '</span>' +
    '<span class="search-result-meta">' + p.position + ' · ' + (FLAGS[p.country] || '') + ' ' + p.country + ' · NDR ' + p.overall.toFixed(1) + '</span>' +
    '</span></button>'
  ).join('');
  dropdown.classList.add('open');
  dropdown.querySelectorAll('.search-result').forEach((btn, i) => {
    btn.onclick = () => goToPlayer(btn.dataset.id);
  });
}

function goToPlayer(id) {
  state.headerSearch = '';
  state.query = '';
  state.searchHighlight = 0;
  closeSearchDropdown();
  location.hash = '/' + draftYear + '/player/' + id;
}

function closeSearchDropdown() {
  const dropdown = document.getElementById('search-dropdown');
  if (dropdown) {
    dropdown.innerHTML = '';
    dropdown.classList.remove('open');
  }
}

function bindGlobalSearch() {
  const input = document.getElementById('global-search');
  if (!input) return;

  let matches = matchPlayersByName(state.headerSearch);

  function syncSearch(rerender) {
    matches = matchPlayersByName(state.headerSearch);
    state.query = state.headerSearch;
    state.listPage = 0;
    if (state.searchHighlight >= matches.length) state.searchHighlight = Math.max(0, matches.length - 1);
    renderSearchDropdown(matches, state.searchHighlight);
    if (rerender && route().page === 'home') {
      const start = input.selectionStart;
      const end = input.selectionEnd;
      render();
      requestAnimationFrame(() => {
        const el = document.getElementById('global-search');
        if (el) {
          el.focus();
          el.setSelectionRange(start, end);
        }
      });
    }
  }

  input.oninput = () => {
    state.headerSearch = input.value;
    state.searchHighlight = 0;
    syncSearch(true);
  };

  input.onkeydown = e => {
    if (e.key === 'Escape') {
      state.headerSearch = '';
      state.query = '';
      input.value = '';
      closeSearchDropdown();
      if (route().page === 'home') render();
      return;
    }
    if (!matches.length) {
      if (e.key === 'Enter') e.preventDefault();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      state.searchHighlight = Math.min(state.searchHighlight + 1, matches.length - 1);
      renderSearchDropdown(matches, state.searchHighlight);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      state.searchHighlight = Math.max(state.searchHighlight - 1, 0);
      renderSearchDropdown(matches, state.searchHighlight);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      goToPlayer(matches[state.searchHighlight].id);
    }
  };

  input.onfocus = () => {
    if (state.headerSearch.trim()) renderSearchDropdown(matches, state.searchHighlight);
  };

  if (!window._searchClickBound) {
    window._searchClickBound = true;
    document.addEventListener('click', e => {
      const w = document.getElementById('global-search-wrap');
      if (w && !w.contains(e.target)) closeSearchDropdown();
    });
  }

  if (state.headerSearch.trim()) renderSearchDropdown(matches, state.searchHighlight);
}

function bindHomeEvents() {
  ['f-pos','f-country','f-tier'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.onchange = e => {
      if (id === 'f-pos') state.position = e.target.value;
      if (id === 'f-country') state.country = e.target.value;
      if (id === 'f-tier') state.tier = e.target.value;
      state.listPage = 0;
      render();
    };
  });
  const min = document.getElementById('f-min');
  if (min) min.oninput = e => {
    state.minScore = +e.target.value;
    state.listPage = 0;
    const lbl = document.getElementById('min-label');
    if (lbl) lbl.textContent = state.minScore;
    render();
  };
  const discovery = document.getElementById('f-discovery');
  if (discovery) discovery.oninput = e => {
    state.minDiscovery = +e.target.value;
    state.listPage = 0;
    const lbl = document.getElementById('discovery-label');
    if (lbl) lbl.textContent = state.minDiscovery;
    render();
  };
  const hidden = document.getElementById('f-hidden');
  if (hidden) hidden.onchange = e => {
    state.hiddenOnly = e.target.checked;
    state.listPage = 0;
    render();
  };
  const prev = document.getElementById('pg-prev');
  const next = document.getElementById('pg-next');
  if (prev) prev.onclick = () => { if (state.listPage > 0) { state.listPage--; render(); } };
  if (next) next.onclick = () => { state.listPage++; render(); };
}

function bindCompareEvents(aId, bId) {
  const sa = document.getElementById('cmp-a');
  const sb = document.getElementById('cmp-b');
  if (sa) { sa.value = aId; sa.onchange = e => { location.hash = `/${draftYear}/compare?a=${e.target.value}&b=${bId}`; }; }
  if (sb) { sb.value = bId; sb.onchange = e => { location.hash = `/${draftYear}/compare?a=${aId}&b=${e.target.value}`; }; }
  document.querySelectorAll('.chip').forEach(chip => {
    chip.onclick = () => {
      const id = chip.dataset.id;
      if (!aId) location.hash = `/${draftYear}/compare?a=${id}&b=${bId}`;
      else if (!bId) location.hash = `/${draftYear}/compare?a=${aId}&b=${id}`;
      else location.hash = `/${draftYear}/compare?a=${id}&b=${bId}`;
    };
  });
}

function bindYearSelector() {
  const sel = document.getElementById('draft-year');
  if (!sel) return;
  sel.onchange = e => switchDraftYear(parseInt(e.target.value, 10));
}

function render() {
  try {
    const r = route();
    if (r.year && r.year !== draftYear) draftYear = r.year;
    const app = document.getElementById('app');
    if (!app) return;

    const meta = currentDraftMeta();
    if (meta.status === 'upcoming' && r.page !== 'compare') {
      app.innerHTML = renderUpcoming();
      bindYearSelector();
      return;
    }

    if (r.page === 'player') {
      app.innerHTML = renderPlayer(r.id);
      bindGlobalSearch();
      bindYearSelector();
    } else if (r.page === 'compare') {
      app.innerHTML = renderCompare(r.a, r.b);
      bindCompareEvents(r.a, r.b);
      bindGlobalSearch();
      bindYearSelector();
      const a = players.find(p => p.id === r.a);
      const b = players.find(p => p.id === r.b);
      if (a && b) requestAnimationFrame(() => drawRadar(a.skills, b.skills));
    } else {
      app.innerHTML = renderHome();
      bindHomeEvents();
      bindGlobalSearch();
      bindYearSelector();
    }
  } catch (e) {
    showError('Erreur affichage: ' + (e.message || String(e)));
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
