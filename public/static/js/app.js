// Stock Predictor - Retro Mac UI JavaScript

// Update clock
function updateClock() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    document.getElementById('clock').textContent = `${hours}:${minutes}`;
}
setInterval(updateClock, 1000);
updateClock();

// Console logging
function logToConsole(message) {
    const console = document.getElementById('console');
    const cursor = console.querySelector('.cursor').parentElement;
    const newLine = document.createElement('div');
    newLine.textContent = `> ${message}`;
    console.insertBefore(newLine, cursor);
    console.scrollTop = console.scrollHeight;
}

// Analyze stock
async function analyzeStock() {
    const symbol = document.getElementById('symbol-input').value.toUpperCase() || 'AAPL';
    const resultDiv = document.getElementById('analysis-result');

    resultDiv.innerHTML = '<p>Analyzing <span class="loading">◐</span></p>';
    logToConsole(`Analyzing ${symbol}...`);

    // Update agent status indicators
    updateAgentStatus('running');

    try {
        const response = await fetch(`/api/analyze?symbol=${symbol}`);
        const data = await response.json();

        if (data.error) {
            resultDiv.innerHTML = `<p style="color: red;">Error: ${data.error}</p>`;
            logToConsole(`Error: ${data.error}`);
            return;
        }

        // Build result HTML
        let html = `
            <div class="stock-card">
                <div class="symbol">${data.symbol}</div>
                <div class="price">$${data.price.toFixed(2)}</div>

                <div class="signal-bar">
                    <span>SELL</span>
                    <div class="bar">
                        <div class="indicator" style="left: ${(data.signal + 1) * 50}%;"></div>
                    </div>
                    <span>BUY</span>
                </div>

                <table class="mac-table" style="margin-top: 12px;">
                    <tr>
                        <td>Technical</td>
                        <td>${formatSignal(data.signals.technical_analyst)}</td>
                    </tr>
                    <tr>
                        <td>Sentiment</td>
                        <td>${formatSignal(data.signals.sentiment_analyst)}</td>
                    </tr>
                    <tr>
                        <td>ML Predictor</td>
                        <td>${formatSignal(data.signals.ml_predictor)}</td>
                    </tr>
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
        resultDiv.innerHTML = `<p>Error connecting to server</p>`;
        logToConsole(`Connection error: ${error.message}`);
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

// Update agent status indicators
function updateAgentStatus(status) {
    const agents = ['ceo', 'risk', 'quant', 'tech', 'fund', 'sent', 'ml'];
    agents.forEach(agent => {
        const el = document.getElementById(`${agent}-status`);
        if (status === 'running') {
            el.textContent = '◐';
            el.className = 'loading';
        } else {
            el.textContent = '●';
            el.className = '';
        }
    });
}

// Refresh portfolio
async function refreshPortfolio() {
    logToConsole('Refreshing portfolio...');

    try {
        const response = await fetch('/api/portfolio');
        const data = await response.json();

        document.getElementById('portfolio-cash').textContent = `$${data.cash.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('portfolio-positions').textContent = `$${data.positions_value.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('portfolio-total').textContent = `$${data.total_value.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
        document.getElementById('portfolio-pnl').textContent = `$${data.total_pnl.toLocaleString('en-US', {minimumFractionDigits: 2})} (${data.total_pnl_pct.toFixed(2)}%)`;

        logToConsole(`Portfolio: $${data.total_value.toLocaleString('en-US', {minimumFractionDigits: 2})}`);

    } catch (error) {
        logToConsole(`Error: ${error.message}`);
    }
}

// Refresh watchlist
async function refreshWatchlist() {
    logToConsole('Refreshing watchlist...');

    const symbols = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA'];
    const tbody = document.getElementById('watchlist-body');

    for (const symbol of symbols) {
        try {
            const response = await fetch(`/api/quote?symbol=${symbol}`);
            const data = await response.json();

            // Find and update the row
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

// Allow Enter key to trigger analysis
document.getElementById('symbol-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        analyzeStock();
    }
});

// Initial load
document.addEventListener('DOMContentLoaded', function() {
    refreshPortfolio();
    logToConsole('Welcome to Stock Predictor');
});
