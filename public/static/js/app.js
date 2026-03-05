// Stock Predictor - Retro Mac UI JavaScript v0.3.0

// ==================== State ====================
// Auth is disabled: everyone uses a shared public account.
// We keep these variables for compatibility but they no longer gate features.
let authToken = 'public';
let isGuest = false;
let cachedAgents = []; // cached agent tree from server

// ==================== Auth (disabled) ====================
function authHeaders() {
    // Backend no longer requires Authorization; keep for compatibility.
    return {};
}

async function apiFetch(url, options = {}) {
    const headers = { ...authHeaders(), ...(options.headers || {}) };
    const resp = await fetch(url, { ...options, headers });
    return resp;
}

// Login / registration / upgrade are no-ops in public mode.
function showLoginDialog() {
    // Auth disabled: nothing to show.
}

function hideLoginDialog() {}

function updateGuestBanner() {
    const banner = document.getElementById('guest-banner');
    if (banner) {
        banner.style.display = 'none';
    }
}

function doLogin() {
    logToConsole('Auth disabled: using public account');
}

function doRegister() {
    logToConsole('Auth disabled: registrations are turned off');
}

function doGuestLogin() {
    logToConsole('Auth disabled: using public account');
}

function doLogout() {
    logToConsole('Auth disabled: staying in public mode');
    onAuthenticated();
}

// ==================== Guest Upgrade (disabled) ====================
function showUpgradeDialog() {
    logToConsole('Upgrade disabled in public mode');
}

function hideUpgradeDialog() {}

function doUpgrade() {
    logToConsole('Upgrade disabled in public mode');
}

// ==================== Clock ====================
function updateClock() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    document.getElementById('clock').textContent = `${hours}:${minutes}`;
}
setInterval(updateClock, 1000);
updateClock();

// ==================== Console ====================
function logToConsole(message) {
    const con = document.getElementById('console');
    const cursor = con.querySelector('.cursor');
    if (!cursor) return;
    const cursorLine = cursor.parentElement;
    const newLine = document.createElement('div');
    newLine.textContent = `> ${message}`;
    con.insertBefore(newLine, cursorLine);
    con.scrollTop = con.scrollHeight;
}

// ==================== Analysis ====================
async function analyzeStock(sym) {
    const symbol = sym || document.getElementById('symbol-input').value.toUpperCase() || 'AAPL';
    const resultDiv = document.getElementById('analysis-result');

    resultDiv.innerHTML = '<p>Analyzing <span class="loading">&#9680;</span></p>';
    logToConsole(`Analyzing ${symbol}...`);

    try {
        const startResp = await apiFetch('/api/analysis/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol }),
        });
        if (!startResp.ok) {
            const err = await startResp.json().catch(() => ({}));
            throw new Error(err.detail || `Server error (${startResp.status})`);
        }
        const { run_id } = await startResp.json();
        logToConsole(`Run ${run_id.slice(0, 8)}... started`);

        let run = null;
        for (let i = 0; i < 60; i++) {
            await new Promise(r => setTimeout(r, 1000));
            const pollResp = await apiFetch(`/api/analysis/run/${run_id}`);
            run = await pollResp.json();
            if (run.status === 'completed' || run.status === 'failed') break;
        }

        if (!run || run.status === 'failed') {
            throw new Error(run?.error_message || 'Analysis failed');
        }

        const signals = {};
        let signalValue = 0;
        for (const out of run.agent_outputs) {
            const sigMap = { buy: 1, hold: 0, sell: -1 };
            const val = (sigMap[out.signal] || 0) * out.confidence;
            signals[out.agent_type] = val;
            signalValue += val;
        }
        signalValue /= (run.agent_outputs.length || 1);

        const data = {
            symbol: run.symbol,
            price: null,
            signal: signalValue,
            confidence: run.final_confidence,
            action: run.final_signal,
            signals,
            outputs: run.agent_outputs,
        };

        try {
            const qResp = await fetch(`/api/quote?symbol=${symbol}`);
            const quote = await qResp.json();
            data.price = quote.price;
        } catch (_) {}

        // Build agent rows dynamically from actual outputs
        let agentRows = '';
        for (const out of run.agent_outputs) {
            const label = out.agent_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            agentRows += `<tr><td>${label}</td><td>${formatSignal(data.signals[out.agent_type])}</td></tr>`;
        }

        let html = `
            <div class="stock-card">
                <div class="symbol">${data.symbol}</div>
                <div class="price">${data.price ? '$' + data.price.toFixed(2) : '--'}</div>
                <div class="signal-bar">
                    <span>SELL</span>
                    <div class="bar">
                        <div class="indicator" style="left: ${(data.signal + 1) * 50}%;"></div>
                    </div>
                    <span>BUY</span>
                </div>
                <table class="mac-table" style="margin-top: 12px;">
                    ${agentRows}
                    <tr>
                        <th>CEO Decision</th>
                        <th class="${data.action === 'buy' ? 'signal-buy' : data.action === 'sell' ? 'signal-sell' : 'signal-hold'}">
                            ${data.action.toUpperCase()}
                        </th>
                    </tr>
                </table>
                <div style="margin-top: 8px;">
                    <small>Confidence: ${(data.confidence * 100).toFixed(0)}%</small>
                </div>
            </div>
        `;
        resultDiv.innerHTML = html;
        logToConsole(`${symbol}: ${data.action.toUpperCase()} (signal: ${data.signal.toFixed(2)})`);
    } catch (error) {
        resultDiv.innerHTML = `<p>Error: ${error.message}</p>`;
        logToConsole(`Error: ${error.message}`);
    }
}

function formatSignal(value) {
    if (value === undefined || value === null) return '--';
    const num = parseFloat(value);
    const sign = num > 0 ? '+' : '';
    const className = num > 0.2 ? 'signal-buy' : num < -0.2 ? 'signal-sell' : 'signal-hold';
    return `<span class="${className}">${sign}${num.toFixed(2)}</span>`;
}

// ==================== Portfolio ====================
async function refreshPortfolio() {
    logToConsole('Refreshing portfolio...');

    try {
        const response = await apiFetch('/api/portfolio');
        if (!response.ok) throw new Error(`Server error (${response.status})`);
        const data = await response.json();

        const fmt = (v) => parseFloat(v).toLocaleString('en-US', {minimumFractionDigits: 2});
        document.getElementById('portfolio-cash').textContent = `$${fmt(data.cash)}`;
        document.getElementById('portfolio-positions').textContent = `$${fmt(data.positions_value)}`;
        document.getElementById('portfolio-total').textContent = `$${fmt(data.total_value)}`;
        document.getElementById('portfolio-pnl').textContent = `$${fmt(data.total_pnl)} (${data.total_pnl_pct.toFixed(2)}%)`;

        logToConsole(`Portfolio: $${fmt(data.total_value)}`);
    } catch (error) {
        logToConsole(`Error: ${error.message}`);
    }
}

// ==================== Watchlist ====================
async function loadWatchlistFromServer() {
    try {
        const resp = await apiFetch('/api/watchlist');
        if (!resp.ok) return;
        const data = await resp.json();
        renderWatchlist(data.symbols);
    } catch (e) {
        console.error('Watchlist load error:', e);
    }
}

function renderWatchlist(symbols) {
    const tbody = document.getElementById('watchlist-body');
    tbody.innerHTML = '';
    for (const sym of symbols) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${sym}</td>
            <td class="wl-price-${sym}">--</td>
            <td>
                <button class="mac-button" style="font-size:11px; padding:1px 6px;" onclick="analyzeStock('${sym}')">Analyze</button>
                <button class="mac-button" style="font-size:11px; padding:1px 6px;" onclick="removeFromWatchlist('${sym}')">X</button>
            </td>
        `;
        tbody.appendChild(tr);
    }
}

async function refreshWatchlist() {
    logToConsole('Refreshing watchlist...');

    try {
        const resp = await apiFetch('/api/watchlist');
        if (!resp.ok) return;
        const data = await resp.json();
        renderWatchlist(data.symbols);

        // Fetch prices
        for (const symbol of data.symbols) {
            try {
                const qResp = await fetch(`/api/quote?symbol=${symbol}`);
                if (!qResp.ok) continue;
                const quote = await qResp.json();
                const cell = document.querySelector(`.wl-price-${symbol}`);
                if (cell) cell.textContent = quote.price ? `$${quote.price.toFixed(2)}` : '--';
            } catch (_) {}
        }
        logToConsole('Watchlist updated');
    } catch (error) {
        logToConsole(`Error: ${error.message}`);
    }
}

async function addToWatchlist(symbol) {
    try {
        await apiFetch(`/api/watchlist/add?symbol=${symbol}`, { method: 'POST' });
        logToConsole(`Added ${symbol} to watchlist`);
        loadWatchlistFromServer();
    } catch (e) {
        logToConsole(`Error: ${e.message}`);
    }
}

async function removeFromWatchlist(symbol) {
    try {
        await apiFetch(`/api/watchlist/remove?symbol=${symbol}`, { method: 'POST' });
        logToConsole(`Removed ${symbol} from watchlist`);
        loadWatchlistFromServer();
    } catch (e) {
        logToConsole(`Error: ${e.message}`);
    }
}

// ==================== Market Browser ====================
let searchTimeout = null;

async function searchStocks(query) {
    if (!query || query.length < 1) {
        document.getElementById('stock-search-results').innerHTML =
            '<p style="color: var(--mac-dark-gray); font-size:13px;">Type to search or browse popular stocks below</p>';
        return;
    }

    try {
        const resp = await fetch(`/api/stocks/search?q=${encodeURIComponent(query)}&limit=15`);
        const data = await resp.json();
        renderStockResults(data.results);
    } catch (e) {
        document.getElementById('stock-search-results').innerHTML = '<p>Search error</p>';
    }
}

async function loadPopularStocks() {
    try {
        const resp = await fetch('/api/stocks/popular?limit=30');
        const data = await resp.json();
        renderStockResults(data.results);
        logToConsole('Loaded popular stocks');
    } catch (e) {
        logToConsole(`Error: ${e.message}`);
    }
}

function renderStockResults(results) {
    const container = document.getElementById('stock-search-results');
    if (!results.length) {
        container.innerHTML = '<p style="color: var(--mac-dark-gray); font-size:13px;">No results</p>';
        return;
    }

    let html = '<table class="mac-table" style="font-size:13px;"><thead><tr><th>Symbol</th><th>Name</th><th>Actions</th></tr></thead><tbody>';
    for (const stock of results) {
        const sectorBadge = stock.sector ? `<br><small style="color:var(--mac-dark-gray);">${stock.sector}</small>` : '';
        html += `<tr>
            <td><strong>${stock.symbol}</strong></td>
            <td>${stock.name}${sectorBadge}</td>
            <td style="white-space:nowrap;">
                <button class="mac-button" style="font-size:11px; padding:1px 5px;" onclick="addToWatchlist('${stock.symbol}')">+Watch</button>
                <button class="mac-button" style="font-size:11px; padding:1px 5px;" onclick="analyzeStock('${stock.symbol}')">Analyze</button>
            </td>
        </tr>`;
    }
    html += '</tbody></table>';
    container.innerHTML = html;
}

// ==================== Portfolio Import ====================
function showImportDialog() {
    document.getElementById('import-overlay').style.display = 'flex';
    document.getElementById('import-error').textContent = '';
    document.getElementById('import-success').textContent = '';
}

function hideImportDialog() {
    document.getElementById('import-overlay').style.display = 'none';
}

async function doImport() {
    const raw = document.getElementById('import-data').value.trim();
    const errorEl = document.getElementById('import-error');
    const successEl = document.getElementById('import-success');
    errorEl.textContent = '';
    successEl.textContent = '';

    if (!raw) { errorEl.textContent = 'Please enter positions'; return; }

    const positions = [];
    const lines = raw.split('\n');
    for (const line of lines) {
        const parts = line.trim().split(',');
        if (parts.length < 3) { errorEl.textContent = `Invalid line: ${line}`; return; }
        const [symbol, shares, avgCost] = parts;
        if (!symbol || isNaN(shares) || isNaN(avgCost)) {
            errorEl.textContent = `Invalid data: ${line}`;
            return;
        }
        positions.push({
            symbol: symbol.trim().toUpperCase(),
            shares: parseFloat(shares.trim()),
            avg_cost: parseFloat(avgCost.trim()),
        });
    }

    try {
        const resp = await apiFetch('/api/portfolio/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ positions }),
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            errorEl.textContent = data.detail || 'Import failed';
            return;
        }
        const data = await resp.json();
        successEl.textContent = data.message;
        logToConsole(`Imported ${data.imported} positions`);
        refreshPortfolio();
    } catch (e) {
        errorEl.textContent = 'Connection error';
    }
}

// ==================== Agent Builder ====================
async function loadAgents() {
    try {
        const resp = await apiFetch('/api/agents');
        if (!resp.ok) return;
        const data = await resp.json();
        cachedAgents = data.agents;
        renderAgentTree(cachedAgents);
    } catch (e) {
        console.error('Agent load error:', e);
    }
}

function renderAgentTree(agents) {
    const container = document.getElementById('agent-tree');
    if (!agents.length) {
        container.innerHTML = '<p style="color: var(--mac-dark-gray);">No agents configured</p>';
        return;
    }

    // Build tree structure
    const agentMap = {};
    agents.forEach(a => agentMap[a.id] = { ...a, children: [] });

    const roots = [];
    agents.forEach(a => {
        if (a.parent_id && agentMap[a.parent_id]) {
            agentMap[a.parent_id].children.push(agentMap[a.id]);
        } else {
            roots.push(agentMap[a.id]);
        }
    });

    let html = '';
    function renderNode(node, depth) {
        const indent = depth * 20;
        const prefix = depth === 0 ? '' : (depth === 1 ? '├─ ' : '└─ ');
        const typeEmoji = {
            ceo: '👔', risk: '🛡', quant: '📊', technical: '📈',
            fundamental: '📋', sentiment: '😤', ml: '🤖', custom: '⚡'
        }[node.agent_type] || '●';

        const enabledClass = node.enabled ? '' : ' style="opacity:0.4;"';
        const weightBadge = node.weight !== 1.0 ? ` <small>[w:${node.weight}]</small>` : '';

        html += `<div class="agent-node" style="margin-left:${indent}px; padding:3px 0; cursor:pointer;"${enabledClass} onclick="editAgent('${node.id}')">`;
        html += `${prefix}<span>${typeEmoji}</span> <strong>${node.name}</strong>${weightBadge}`;
        if (node.prompt) {
            const shortPrompt = node.prompt.length > 40 ? node.prompt.slice(0, 40) + '...' : node.prompt;
            html += `<br><small style="margin-left:${indent + 20}px; color:var(--mac-dark-gray);">${shortPrompt}</small>`;
        }
        html += '</div>';

        // Sort children by sort_order
        node.children.sort((a, b) => a.sort_order - b.sort_order);
        node.children.forEach(child => renderNode(child, depth + 1));
    }

    roots.sort((a, b) => a.sort_order - b.sort_order);
    roots.forEach(root => renderNode(root, 0));

    container.innerHTML = html;
}

function editAgent(agentId) {
    const agent = cachedAgents.find(a => a.id === agentId);
    if (!agent) return;

    document.getElementById('agent-edit-id').value = agent.id;
    document.getElementById('agent-edit-name').value = agent.name;
    document.getElementById('agent-edit-prompt').value = agent.prompt || '';
    document.getElementById('agent-edit-weight').value = agent.weight;
    document.getElementById('agent-edit-weight-label').textContent = agent.weight;
    document.getElementById('agent-edit-enabled').checked = agent.enabled;
    document.getElementById('agent-edit-error').textContent = '';
    document.getElementById('agent-edit-overlay').style.display = 'flex';
}

function hideAgentEditDialog() {
    document.getElementById('agent-edit-overlay').style.display = 'none';
}

async function saveAgent() {
    const id = document.getElementById('agent-edit-id').value;
    const errorEl = document.getElementById('agent-edit-error');
    errorEl.textContent = '';

    const body = {
        name: document.getElementById('agent-edit-name').value,
        prompt: document.getElementById('agent-edit-prompt').value || null,
        weight: parseFloat(document.getElementById('agent-edit-weight').value),
        enabled: document.getElementById('agent-edit-enabled').checked,
    };

    try {
        const resp = await apiFetch(`/api/agents/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            errorEl.textContent = data.detail || 'Save failed';
            return;
        }
        hideAgentEditDialog();
        logToConsole(`Agent "${body.name}" updated`);
        loadAgents();
    } catch (e) {
        errorEl.textContent = 'Connection error';
    }
}

async function deleteAgent() {
    const id = document.getElementById('agent-edit-id').value;
    const name = document.getElementById('agent-edit-name').value;

    try {
        const resp = await apiFetch(`/api/agents/${id}`, { method: 'DELETE' });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            document.getElementById('agent-edit-error').textContent = data.detail || 'Delete failed';
            return;
        }
        hideAgentEditDialog();
        logToConsole(`Agent "${name}" deleted`);
        loadAgents();
    } catch (e) {
        document.getElementById('agent-edit-error').textContent = 'Connection error';
    }
}

async function resetAgents() {
    try {
        const resp = await apiFetch('/api/agents/reset', { method: 'POST' });
        if (resp.ok) {
            logToConsole('Agent hierarchy reset to defaults');
            loadAgents();
        }
    } catch (e) {
        logToConsole(`Error: ${e.message}`);
    }
}

function showAddAgentDialog() {
    document.getElementById('agent-add-name').value = '';
    document.getElementById('agent-add-prompt').value = '';
    document.getElementById('agent-add-error').textContent = '';

    // Populate parent dropdown
    const parentSelect = document.getElementById('agent-add-parent');
    parentSelect.innerHTML = '<option value="">(Top Level)</option>';
    for (const agent of cachedAgents) {
        parentSelect.innerHTML += `<option value="${agent.id}">${agent.name}</option>`;
    }

    document.getElementById('agent-add-overlay').style.display = 'flex';
}

function hideAddAgentDialog() {
    document.getElementById('agent-add-overlay').style.display = 'none';
}

async function addAgent() {
    const errorEl = document.getElementById('agent-add-error');
    errorEl.textContent = '';

    const name = document.getElementById('agent-add-name').value.trim();
    if (!name) { errorEl.textContent = 'Name is required'; return; }

    const body = {
        name,
        agent_type: document.getElementById('agent-add-type').value,
        parent_id: document.getElementById('agent-add-parent').value || null,
        prompt: document.getElementById('agent-add-prompt').value || null,
        weight: 1.0,
        sort_order: cachedAgents.length,
    };

    try {
        const resp = await apiFetch('/api/agents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            errorEl.textContent = data.detail || 'Create failed';
            return;
        }
        hideAddAgentDialog();
        logToConsole(`Agent "${name}" created`);
        loadAgents();
    } catch (e) {
        errorEl.textContent = 'Connection error';
    }
}

// ==================== Post-Auth Init ====================
function onAuthenticated() {
    refreshPortfolio();
    loadWatchlistFromServer();
    loadAgents();
}

// ==================== Event Listeners ====================
document.getElementById('symbol-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') analyzeStock();
});

// Login dialog is disabled; guard in case elements are missing.
const loginPasswordInput = document.getElementById('login-password');
if (loginPasswordInput) {
    loginPasswordInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') doLogin();
    });
}

document.getElementById('stock-search').addEventListener('input', function(e) {
    clearTimeout(searchTimeout);
    const query = e.target.value.trim();
    searchTimeout = setTimeout(() => searchStocks(query), 300);
});

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', function() {
    updateGuestBanner();
    onAuthenticated();
    logToConsole('Welcome to Stock Predictor');
});
