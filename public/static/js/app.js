// Stock Predictor - Retro Mac UI JavaScript

// ==================== Auth ====================
let authToken = localStorage.getItem('sp_token');

function authHeaders() {
    if (!authToken) return {};
    return { 'Authorization': `Bearer ${authToken}` };
}

async function apiFetch(url, options = {}) {
    const headers = { ...authHeaders(), ...(options.headers || {}) };
    const resp = await fetch(url, { ...options, headers });
    if (resp.status === 401) {
        authToken = null;
        localStorage.removeItem('sp_token');
        showLoginDialog();
        throw new Error('Session expired. Please log in.');
    }
    return resp;
}

function showLoginDialog() {
    document.getElementById('login-overlay').style.display = 'flex';
}

function hideLoginDialog() {
    document.getElementById('login-overlay').style.display = 'none';
    document.getElementById('login-error').textContent = '';
}

async function doLogin() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = '';

    try {
        const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            errorEl.textContent = data.detail || 'Login failed';
            return;
        }
        const data = await resp.json();
        authToken = data.access_token;
        localStorage.setItem('sp_token', authToken);
        hideLoginDialog();
        logToConsole('Logged in successfully');
        refreshPortfolio();
    } catch (e) {
        errorEl.textContent = 'Connection error';
    }
}

async function doRegister() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');
    errorEl.textContent = '';

    try {
        const resp = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            errorEl.textContent = data.detail || 'Registration failed';
            return;
        }
        const data = await resp.json();
        authToken = data.access_token;
        localStorage.setItem('sp_token', authToken);
        hideLoginDialog();
        logToConsole('Account created successfully');
        refreshPortfolio();
    } catch (e) {
        errorEl.textContent = 'Connection error';
    }
}

function doLogout() {
    authToken = null;
    localStorage.removeItem('sp_token');
    logToConsole('Logged out');
    document.getElementById('portfolio-cash').textContent = '--';
    document.getElementById('portfolio-positions').textContent = '--';
    document.getElementById('portfolio-total').textContent = '--';
    document.getElementById('portfolio-pnl').textContent = '--';
    showLoginDialog();
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
    const cursor = con.querySelector('.cursor').parentElement;
    const newLine = document.createElement('div');
    newLine.textContent = `> ${message}`;
    con.insertBefore(newLine, cursor);
    con.scrollTop = con.scrollHeight;
}

// ==================== Analysis ====================
async function analyzeStock() {
    const symbol = document.getElementById('symbol-input').value.toUpperCase() || 'AAPL';
    const resultDiv = document.getElementById('analysis-result');

    if (!authToken) { showLoginDialog(); return; }

    resultDiv.innerHTML = '<p>Analyzing <span class="loading">&#9680;</span></p>';
    logToConsole(`Analyzing ${symbol}...`);
    updateAgentStatus('running');

    try {
        // Start analysis run
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

        // Poll for completion
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

        // Build signals map from agent outputs
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
            price: run.agent_outputs[0]?.reasoning?.rsi ? null : null, // Price from quote
            signal: signalValue,
            confidence: run.final_confidence,
            action: run.final_signal,
            signals,
        };

        // Fetch current price for display
        try {
            const qResp = await fetch(`/api/quote?symbol=${symbol}`);
            const quote = await qResp.json();
            data.price = quote.price;
        } catch (_) {}

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
                    <tr><td>Technical</td><td>${formatSignal(data.signals.technical_analyst)}</td></tr>
                    <tr><td>Fundamental</td><td>${formatSignal(data.signals.fundamental_analyst)}</td></tr>
                    <tr><td>Sentiment</td><td>${formatSignal(data.signals.sentiment_analyst)}</td></tr>
                    <tr><td>ML Predictor</td><td>${formatSignal(data.signals.ml_predictor)}</td></tr>
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

    updateAgentStatus('idle');
}

function formatSignal(value) {
    if (value === undefined || value === null) return '--';
    const num = parseFloat(value);
    const sign = num > 0 ? '+' : '';
    const className = num > 0.2 ? 'signal-buy' : num < -0.2 ? 'signal-sell' : 'signal-hold';
    return `<span class="${className}">${sign}${num.toFixed(2)}</span>`;
}

function updateAgentStatus(status) {
    const agents = ['ceo', 'risk', 'quant', 'tech', 'fund', 'sent', 'ml'];
    agents.forEach(agent => {
        const el = document.getElementById(`${agent}-status`);
        if (status === 'running') {
            el.textContent = '\u25D0';
            el.className = 'loading';
        } else {
            el.textContent = '\u25CF';
            el.className = '';
        }
    });
}

// ==================== Portfolio ====================
async function refreshPortfolio() {
    if (!authToken) return;
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
async function refreshWatchlist() {
    logToConsole('Refreshing watchlist...');

    const symbols = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'];
    const tbody = document.getElementById('watchlist-body');

    for (const symbol of symbols) {
        try {
            const response = await fetch(`/api/quote?symbol=${symbol}`);
            if (!response.ok) throw new Error(`Server error (${response.status})`);
            const data = await response.json();

            const rows = tbody.getElementsByTagName('tr');
            for (const row of rows) {
                if (row.cells[0].textContent === symbol) {
                    row.cells[1].textContent = data.price ? `$${data.price.toFixed(2)}` : '--';
                    break;
                }
            }
        } catch (error) {
            console.error(`Error fetching ${symbol}:`, error);
        }
    }
    logToConsole('Watchlist updated');
}

// ==================== Event Listeners ====================
document.getElementById('symbol-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') analyzeStock();
});

document.getElementById('login-password').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') doLogin();
});

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', function() {
    if (!authToken) {
        showLoginDialog();
    } else {
        refreshPortfolio();
    }
    logToConsole('Welcome to Stock Predictor');
});
