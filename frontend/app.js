const API = '';

// Navigation
document.querySelectorAll('.nav-links a').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const target = link.getAttribute('href').slice(1);
    document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
    link.classList.add('active');
    document.querySelectorAll('section').forEach(s => s.classList.remove('active'));
    document.getElementById(target).classList.add('active');
    if (target === 'strategies') loadStrategies();
    if (target === 'status') loadStatus();
  });
});

// --- Query ---
const queryInput = document.getElementById('query-input');
const queryBtn = document.getElementById('query-btn');
const queryStatus = document.getElementById('query-status');
const queryResult = document.getElementById('query-result');

queryBtn.addEventListener('click', runQuery);
queryInput.addEventListener('keydown', e => { if (e.key === 'Enter') runQuery(); });

async function runQuery() {
  const q = queryInput.value.trim();
  if (!q) return;
  queryStatus.className = 'status-msg ok';
  queryStatus.textContent = 'Running pipeline...';
  queryResult.classList.add('hidden');
  try {
    const res = await fetch(`${API}/api/pipeline/run-with-search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q }),
    });
    if (!res.ok) { queryStatus.className = 'status-msg err'; queryStatus.textContent = `Error ${res.status}`; return; }
    const data = await res.json();
    queryStatus.className = 'status-msg ok';
    queryStatus.textContent = `Status: ${data.result.status} | Source: ${data.result.source || 'N/A'} | Qdrant hits: ${data.qdrant_hits}`;
    queryResult.classList.remove('hidden');
    queryResult.innerHTML = `<h3>Result</h3><pre>${escapeHtml(JSON.stringify(data.result, null, 2))}</pre>`;
  } catch (err) {
    queryStatus.className = 'status-msg err';
    queryStatus.textContent = `Request failed: ${err.message}`;
  }
}

// --- Strategies ---
const strategyList = document.getElementById('strategy-list');
const strategyCount = document.getElementById('strategy-count');
const strategyDetail = document.getElementById('strategy-detail');
const refreshBtn = document.getElementById('refresh-strategies');

refreshBtn.addEventListener('click', loadStrategies);

async function loadStrategies() {
  strategyDetail.classList.add('hidden');
  strategyList.innerHTML = '<p>Loading...</p>';
  try {
    const res = await fetch(`${API}/api/strategies?limit=100`);
    if (!res.ok) { strategyList.innerHTML = '<p class="err">Failed to load</p>'; return; }
    const data = await res.json();
    strategyCount.textContent = `Showing ${data.data.length} of ${data.total} strategies`;
    if (!data.data.length) { strategyList.innerHTML = '<p>No strategies found.</p>'; return; }
    let html = '<table><thead><tr><th>Name</th><th>Category</th><th>Indicator</th><th>Slug</th><th>Created</th></tr></thead><tbody>';
    for (const row of data.data) {
      html += `<tr class="clickable" data-id="${escapeHtml(row.id)}">
        <td>${escapeHtml(row.name || 'Unnamed')}</td>
        <td><span class="badge green">${escapeHtml(row.category || '—')}</span></td>
        <td><span class="badge purple">${escapeHtml(row.indicator || '—')}</span></td>
        <td>${escapeHtml(row.slug || '—')}</td>
        <td>${row.created_at ? new Date(row.created_at).toLocaleDateString() : '—'}</td>
      </tr>`;
    }
    html += '</tbody></table>';
    strategyList.innerHTML = html;
    document.querySelectorAll('#strategy-list tr.clickable').forEach(tr => {
      tr.addEventListener('click', () => loadStrategyDetail(tr.dataset.id));
    });
  } catch (err) {
    strategyList.innerHTML = `<p class="err">${escapeHtml(err.message)}</p>`;
  }
}

async function loadStrategyDetail(id) {
  strategyDetail.classList.remove('hidden');
  strategyDetail.innerHTML = '<h3>Loading...</h3>';
  try {
    const res = await fetch(`${API}/api/strategies/${id}`);
    const data = await res.json();
    strategyDetail.innerHTML = `<h3>${escapeHtml(data.data.name || 'Unnamed')}</h3>
      <pre>${escapeHtml(JSON.stringify(data.data, null, 2))}</pre>`;
  } catch (err) {
    strategyDetail.innerHTML = `<p class="err">${escapeHtml(err.message)}</p>`;
  }
}

// --- Search ---
const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const searchStatus = document.getElementById('search-status');
const searchResults = document.getElementById('search-results');

searchBtn.addEventListener('click', runSearch);
searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(); });

async function runSearch() {
  const q = searchInput.value.trim();
  if (!q) return;
  searchStatus.textContent = 'Searching...';
  searchStatus.className = 'status-msg ok';
  searchResults.classList.add('hidden');
  try {
    const res = await fetch(`${API}/api/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: q, limit: 10 }),
    });
    if (!res.ok) { searchStatus.className = 'status-msg err'; searchStatus.textContent = `Error ${res.status}`; return; }
    const data = await res.json();
    searchStatus.className = 'status-msg ok';
    searchStatus.textContent = `Found ${data.results.length} results`;
    searchResults.classList.remove('hidden');
    let html = '';
    for (const hit of data.results) {
      const name = hit.payload?.name || hit.payload?.strategy_name || 'Unnamed';
      html += `<div class="result-item">
        <div><strong>${escapeHtml(name)}</strong> <span class="badge yellow">${hit.score.toFixed(3)}</span>
        <span class="badge green">${hit.collection}</span></div>
        <pre>${escapeHtml(JSON.stringify(hit.payload || {}, null, 2))}</pre>
      </div>`;
    }
    searchResults.innerHTML = html;
  } catch (err) {
    searchStatus.className = 'status-msg err';
    searchStatus.textContent = `Search failed: ${err.message}`;
  }
}

// --- Status ---
async function loadStatus() {
  const healthPanel = document.getElementById('health-panel');
  const statsPanel = document.getElementById('db-stats-panel');

  healthPanel.innerHTML = '<p>Loading health...</p>';
  statsPanel.innerHTML = '';

  try {
    const healthRes = await fetch(`${API}/api/health`);
    const health = await healthRes.json();
    const checks = health.checks || {};
    healthPanel.innerHTML = `<h3>Service Health</h3>
      <div class="health-grid">
        <div class="health-card"><div class="label">PostgreSQL</div><div class="value ${checks.postgresql ? 'up' : 'down'}">${checks.postgresql ? 'Up' : 'Down'}</div></div>
        <div class="health-card"><div class="label">Qdrant</div><div class="value ${checks.qdrant ? 'up' : 'down'}">${checks.qdrant ? 'Up' : 'Down'}</div></div>
        <div class="health-card"><div class="label">Overall</div><div class="value ${health.status === 'ok' ? 'up' : 'down'}">${health.status === 'ok' ? 'Healthy' : 'Degraded'}</div></div>

      </div>`;
  } catch (err) {
    healthPanel.innerHTML = `<p class="err">Health check failed: ${escapeHtml(err.message)}</p>`;
  }

  try {
    const statsRes = await fetch(`${API}/api/db/stats`);
    const stats = await statsRes.json();
    let html = '<h3>Database Row Counts</h3><div class="stats-grid">';
    for (const [name, count] of Object.entries(stats.data)) {
      html += `<div class="stat-card"><span class="name">${escapeHtml(name)}</span><span class="count">${count}</span></div>`;
    }
    html += '</div>';
    statsPanel.innerHTML = html;
  } catch (err) {
    statsPanel.innerHTML = `<p class="err">Stats failed: ${escapeHtml(err.message)}</p>`;
  }
}

function escapeHtml(str) {
  if (str == null) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

// Load initial data
setTimeout(() => { loadStrategies(); loadStatus(); }, 500);
