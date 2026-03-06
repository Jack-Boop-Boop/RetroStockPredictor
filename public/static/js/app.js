// Stock Predictor - Retro Mac UI JavaScript v1.0.0
// Single-user, localStorage-only MVP

// ==================== State Management ====================
const DEFAULTS = {
    watchlist: ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'NVDA'],
    cash: 100000,
    positions: {},
    orders: [],
};

let state = { watchlist: [], cash: 0, positions: {}, orders: [] };
let tradeSide = 'buy';

function loadState() {
    try {
        state.watchlist = JSON.parse(localStorage.getItem('sp_watchlist')) || [...DEFAULTS.watchlist];
        state.cash = parseFloat(localStorage.getItem('sp_cash')) || DEFAULTS.cash;
        state.positions = JSON.parse(localStorage.getItem('sp_positions')) || {};
        state.orders = JSON.parse(localStorage.getItem('sp_orders')) || [];
    } catch (e) {
        console.error('State load error, resetting:', e);
        state = { watchlist: [...DEFAULTS.watchlist], cash: DEFAULTS.cash, positions: {}, orders: [] };
    }
}

function saveState() {
    localStorage.setItem('sp_watchlist', JSON.stringify(state.watchlist));
    localStorage.setItem('sp_cash', state.cash.toString());
    localStorage.setItem('sp_positions', JSON.stringify(state.positions));
    localStorage.setItem('sp_orders', JSON.stringify(state.orders));
}

function resetState() {
    if (!confirm('Reset all data? This will clear your portfolio, orders, and watchlist.')) return;
    localStorage.removeItem('sp_watchlist');
    localStorage.removeItem('sp_cash');
    localStorage.removeItem('sp_positions');
    localStorage.removeItem('sp_orders');
    location.reload();
}

// ==================== API Helpers ====================
async function fetchQuote(symbol) {
    const resp = await fetch(`/api/quote?symbol=${encodeURIComponent(symbol)}`);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `Quote failed (${resp.status})`);
    }
    return resp.json();
}

async function fetchHistory(symbol, period = '3mo') {
    const resp = await fetch(`/api/history?symbol=${encodeURIComponent(symbol)}&period=${period}`);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `History failed (${resp.status})`);
    }
    return resp.json();
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

// ==================== Watchlist ====================
function renderWatchlist() {
    const tbody = document.getElementById('watchlist-body');
    tbody.innerHTML = '';
    for (const sym of state.watchlist) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${sym}</strong></td>
            <td class="wl-price" data-sym="${sym}">--</td>
            <td class="wl-change" data-sym="${sym}">--</td>
            <td style="white-space:nowrap;">
                <button class="mac-button" style="font-size:11px; padding:1px 5px;" onclick="analyzeStock('${sym}')">Analyze</button>
                <button class="mac-button" style="font-size:11px; padding:1px 5px;" onclick="prefillTrade('${sym}')">Trade</button>
                <button class="mac-button" style="font-size:11px; padding:1px 5px;" onclick="removeSymbol('${sym}')">X</button>
            </td>
        `;
        tbody.appendChild(tr);
    }
}

async function refreshWatchlistPrices() {
    logToConsole('Refreshing watchlist prices...');
    for (const sym of state.watchlist) {
        try {
            const quote = await fetchQuote(sym);
            const priceCell = document.querySelector(`.wl-price[data-sym="${sym}"]`);
            const changeCell = document.querySelector(`.wl-change[data-sym="${sym}"]`);

            if (priceCell && quote.price) {
                priceCell.textContent = `$${quote.price.toFixed(2)}`;
            }
            if (changeCell && quote.change != null) {
                const arrow = quote.change >= 0 ? '\u25B2' : '\u25BC';
                const cls = quote.change >= 0 ? 'change-up' : 'change-down';
                changeCell.innerHTML = `<span class="${cls}">${arrow} $${Math.abs(quote.change).toFixed(2)} (${Math.abs(quote.change_pct).toFixed(2)}%)</span>`;
            }
        } catch (e) {
            console.error(`Quote error for ${sym}:`, e);
        }
    }
    logToConsole('Watchlist updated');
}

function addSymbolFromInput() {
    const input = document.getElementById('add-symbol-input');
    const sym = input.value.trim().toUpperCase();
    if (!sym) return;
    addSymbol(sym);
    input.value = '';
}

function addSymbol(sym) {
    if (state.watchlist.includes(sym)) {
        logToConsole(`${sym} already in watchlist`);
        return;
    }
    state.watchlist.push(sym);
    saveState();
    renderWatchlist();
    logToConsole(`Added ${sym} to watchlist`);
    // Fetch price for the new symbol
    refreshSingleQuote(sym);
}

function removeSymbol(sym) {
    state.watchlist = state.watchlist.filter(s => s !== sym);
    saveState();
    renderWatchlist();
    logToConsole(`Removed ${sym} from watchlist`);
    // Re-render prices for remaining symbols
    refreshWatchlistPrices();
}

async function refreshSingleQuote(sym) {
    try {
        const quote = await fetchQuote(sym);
        const priceCell = document.querySelector(`.wl-price[data-sym="${sym}"]`);
        const changeCell = document.querySelector(`.wl-change[data-sym="${sym}"]`);

        if (priceCell && quote.price) {
            priceCell.textContent = `$${quote.price.toFixed(2)}`;
        }
        if (changeCell && quote.change != null) {
            const arrow = quote.change >= 0 ? '\u25B2' : '\u25BC';
            const cls = quote.change >= 0 ? 'change-up' : 'change-down';
            changeCell.innerHTML = `<span class="${cls}">${arrow} $${Math.abs(quote.change).toFixed(2)} (${Math.abs(quote.change_pct).toFixed(2)}%)</span>`;
        }
    } catch (e) {
        console.error(`Quote error for ${sym}:`, e);
    }
}

// ==================== Portfolio Display ====================
const fmt = (v) => parseFloat(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function renderPortfolio() {
    const cashEl = document.getElementById('portfolio-cash');
    const posEl = document.getElementById('portfolio-positions');
    const totalEl = document.getElementById('portfolio-total');
    const pnlEl = document.getElementById('portfolio-pnl');
    const listEl = document.getElementById('positions-list');

    cashEl.textContent = `$${fmt(state.cash)}`;

    const syms = Object.keys(state.positions);
    if (syms.length === 0) {
        posEl.textContent = '$0.00';
        totalEl.textContent = `$${fmt(state.cash)}`;
        pnlEl.textContent = '$0.00 (0.00%)';
        listEl.innerHTML = '';
        return;
    }

    let positionsValue = 0;
    let costBasis = 0;
    let posHtml = '<table class="mac-table" style="font-size:12px;"><tr><th>Sym</th><th>Shares</th><th>Avg Cost</th><th>Value</th></tr>';

    for (const sym of syms) {
        const pos = state.positions[sym];
        let curPrice = pos.avgCost; // fallback
        try {
            const quote = await fetchQuote(sym);
            if (quote.price) curPrice = quote.price;
        } catch (_) {}

        const val = pos.shares * curPrice;
        const cost = pos.shares * pos.avgCost;
        positionsValue += val;
        costBasis += cost;
        posHtml += `<tr><td>${sym}</td><td>${pos.shares}</td><td>$${fmt(pos.avgCost)}</td><td>$${fmt(val)}</td></tr>`;
    }
    posHtml += '</table>';

    const total = state.cash + positionsValue;
    const pnl = positionsValue - costBasis;
    const pnlPct = costBasis > 0 ? (pnl / costBasis) * 100 : 0;

    posEl.textContent = `$${fmt(positionsValue)}`;
    totalEl.textContent = `$${fmt(total)}`;
    pnlEl.textContent = `$${fmt(pnl)} (${pnlPct.toFixed(2)}%)`;
    listEl.innerHTML = posHtml;
}

// ==================== Paper Trading ====================
function setTradeSide(side) {
    tradeSide = side;
    document.getElementById('trade-buy-btn').classList.toggle('active', side === 'buy');
    document.getElementById('trade-sell-btn').classList.toggle('active', side === 'sell');
}

function prefillTrade(sym) {
    document.getElementById('trade-symbol').value = sym;
    document.getElementById('trade-shares').value = '';
    document.getElementById('trade-error').textContent = '';
    document.getElementById('trade-success').textContent = '';
}

async function executeTrade() {
    const symbol = document.getElementById('trade-symbol').value.trim().toUpperCase();
    const sharesStr = document.getElementById('trade-shares').value;
    const errorEl = document.getElementById('trade-error');
    const successEl = document.getElementById('trade-success');
    errorEl.textContent = '';
    successEl.textContent = '';

    if (!symbol) { errorEl.textContent = 'Enter a symbol'; return; }
    const shares = parseInt(sharesStr);
    if (!shares || shares <= 0) { errorEl.textContent = 'Enter valid number of shares'; return; }

    // Fetch current price
    let price;
    try {
        errorEl.textContent = 'Fetching price...';
        const quote = await fetchQuote(symbol);
        price = quote.price;
        if (!price) throw new Error('Price unavailable');
        errorEl.textContent = '';
    } catch (e) {
        errorEl.textContent = `Cannot get price: ${e.message}`;
        return;
    }

    if (tradeSide === 'buy') {
        const cost = shares * price;
        if (cost > state.cash) {
            errorEl.textContent = `Insufficient cash. Need $${fmt(cost)}, have $${fmt(state.cash)}`;
            return;
        }
        state.cash -= cost;

        if (state.positions[symbol]) {
            const pos = state.positions[symbol];
            const totalShares = pos.shares + shares;
            pos.avgCost = ((pos.shares * pos.avgCost) + cost) / totalShares;
            pos.shares = totalShares;
        } else {
            state.positions[symbol] = { shares, avgCost: price };
        }

        successEl.textContent = `Bought ${shares} ${symbol} @ $${price.toFixed(2)}`;
        logToConsole(`BUY ${shares} ${symbol} @ $${price.toFixed(2)} = $${cost.toFixed(2)}`);

    } else {
        // Sell
        const pos = state.positions[symbol];
        if (!pos || pos.shares < shares) {
            const have = pos ? pos.shares : 0;
            errorEl.textContent = `Insufficient shares. Have ${have}, trying to sell ${shares}`;
            return;
        }

        const proceeds = shares * price;
        state.cash += proceeds;
        pos.shares -= shares;

        if (pos.shares === 0) {
            delete state.positions[symbol];
        }

        successEl.textContent = `Sold ${shares} ${symbol} @ $${price.toFixed(2)}`;
        logToConsole(`SELL ${shares} ${symbol} @ $${price.toFixed(2)} = $${proceeds.toFixed(2)}`);
    }

    // Record order
    state.orders.unshift({
        id: Date.now(),
        symbol,
        side: tradeSide,
        shares,
        price,
        timestamp: new Date().toISOString(),
    });

    // Keep only last 50 orders
    if (state.orders.length > 50) state.orders = state.orders.slice(0, 50);

    saveState();
    renderOrders();
    renderPortfolio();
}

function renderOrders() {
    const el = document.getElementById('orders-list');
    if (state.orders.length === 0) {
        el.innerHTML = '<p style="color: var(--mac-dark-gray); font-size: 12px;">No orders yet</p>';
        return;
    }

    let html = '<table class="mac-table" style="font-size:11px;"><tr><th>Time</th><th>Side</th><th>Sym</th><th>Shares</th><th>Price</th></tr>';
    for (const order of state.orders.slice(0, 20)) {
        const time = new Date(order.timestamp).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        const sideClass = order.side === 'buy' ? 'signal-buy' : 'signal-sell';
        html += `<tr>
            <td>${time}</td>
            <td class="${sideClass}">${order.side.toUpperCase()}</td>
            <td>${order.symbol}</td>
            <td>${order.shares}</td>
            <td>$${order.price.toFixed(2)}</td>
        </tr>`;
    }
    html += '</table>';
    el.innerHTML = html;
}

// ==================== Analysis ====================
function computeSMA(closes, period) {
    if (closes.length < period) return null;
    const slice = closes.slice(-period);
    return slice.reduce((sum, v) => sum + v, 0) / period;
}

function computeRSI(closes, period = 14) {
    if (closes.length < period + 1) return null;

    let avgGain = 0;
    let avgLoss = 0;

    // Initial average gain/loss
    for (let i = 1; i <= period; i++) {
        const change = closes[i] - closes[i - 1];
        if (change > 0) avgGain += change;
        else avgLoss += Math.abs(change);
    }
    avgGain /= period;
    avgLoss /= period;

    // Wilder's smoothing for remaining data
    for (let i = period + 1; i < closes.length; i++) {
        const change = closes[i] - closes[i - 1];
        if (change > 0) {
            avgGain = (avgGain * (period - 1) + change) / period;
            avgLoss = (avgLoss * (period - 1)) / period;
        } else {
            avgGain = (avgGain * (period - 1)) / period;
            avgLoss = (avgLoss * (period - 1) + Math.abs(change)) / period;
        }
    }

    if (avgLoss === 0) return 100;
    const rs = avgGain / avgLoss;
    return 100 - (100 / (1 + rs));
}

function getSignal(price, sma20, sma50, rsi) {
    if (sma20 === null || sma50 === null || rsi === null) {
        return { signal: 'HOLD', reason: 'Insufficient data for analysis.' };
    }

    // SELL: price < SMA20 < SMA50 OR RSI > 80
    if ((price < sma20 && sma20 < sma50) || rsi > 80) {
        let reason = '';
        if (price < sma20 && sma20 < sma50) {
            reason = `Price ($${price.toFixed(2)}) is below both moving averages, indicating a downtrend.`;
        }
        if (rsi > 80) {
            reason += (reason ? ' ' : '') + `RSI at ${rsi.toFixed(1)} signals overbought conditions.`;
        }
        return { signal: 'SELL', reason };
    }

    // BUY: price > SMA20 > SMA50 AND RSI < 70
    if (price > sma20 && sma20 > sma50 && rsi < 70) {
        return {
            signal: 'BUY',
            reason: `Price ($${price.toFixed(2)}) is above both moving averages with RSI at ${rsi.toFixed(1)}, indicating bullish momentum.`,
        };
    }

    // HOLD
    return {
        signal: 'HOLD',
        reason: `Mixed signals: SMA20 ($${sma20.toFixed(2)}), SMA50 ($${sma50.toFixed(2)}), RSI ${rsi.toFixed(1)}. No clear trend.`,
    };
}

async function analyzeStock(sym) {
    const symbol = (sym || document.getElementById('symbol-input').value.trim().toUpperCase()) || 'AAPL';
    const resultDiv = document.getElementById('analysis-result');

    resultDiv.innerHTML = '<p>Analyzing <span class="loading">&#9680;</span></p>';
    logToConsole(`Analyzing ${symbol}...`);

    try {
        // Fetch history and quote in parallel
        const [histData, quoteData] = await Promise.all([
            fetchHistory(symbol, '3mo'),
            fetchQuote(symbol),
        ]);

        const closes = histData.closes.map(c => c[1]); // extract close prices
        const price = quoteData.price;

        if (!price) throw new Error('Price unavailable');
        if (closes.length < 50) throw new Error(`Only ${closes.length} days of data. Need at least 50.`);

        const sma20 = computeSMA(closes, 20);
        const sma50 = computeSMA(closes, 50);
        const rsi = computeRSI(closes, 14);
        const { signal, reason } = getSignal(price, sma20, sma50, rsi);

        const signalClass = signal === 'BUY' ? 'signal-buy' : signal === 'SELL' ? 'signal-sell' : 'signal-hold';

        // Signal bar: map BUY=80%, SELL=20%, HOLD=50%
        const barPos = signal === 'BUY' ? 80 : signal === 'SELL' ? 20 : 50;

        const changeStr = quoteData.change != null
            ? `${quoteData.change >= 0 ? '\u25B2' : '\u25BC'} $${Math.abs(quoteData.change).toFixed(2)} (${Math.abs(quoteData.change_pct).toFixed(2)}%)`
            : '';

        const html = `
            <div class="stock-card">
                <div class="symbol">${symbol}</div>
                <div class="price">$${price.toFixed(2)} <span style="font-size:14px;">${changeStr}</span></div>
                <div class="signal-bar">
                    <span>SELL</span>
                    <div class="bar">
                        <div class="indicator" style="left: ${barPos}%;"></div>
                    </div>
                    <span>BUY</span>
                </div>
                <table class="mac-table" style="margin-top: 12px;">
                    <tr><td>SMA 20</td><td>$${sma20 ? sma20.toFixed(2) : '--'}</td></tr>
                    <tr><td>SMA 50</td><td>$${sma50 ? sma50.toFixed(2) : '--'}</td></tr>
                    <tr><td>RSI 14</td><td>${rsi ? rsi.toFixed(1) : '--'}</td></tr>
                    <tr>
                        <th>Signal</th>
                        <th class="${signalClass}">${signal}</th>
                    </tr>
                </table>
                <div style="margin-top: 8px; font-size: 13px;">
                    ${reason}
                </div>
            </div>
        `;
        resultDiv.innerHTML = html;
        logToConsole(`${symbol}: ${signal} (SMA20: $${sma20.toFixed(2)}, RSI: ${rsi.toFixed(1)})`);

    } catch (error) {
        resultDiv.innerHTML = `<p style="color:red;">Error: ${error.message}</p>`;
        logToConsole(`Error: ${error.message}`);
    }
}

// ==================== Event Listeners ====================
document.getElementById('symbol-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') analyzeStock();
});

document.getElementById('add-symbol-input').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') addSymbolFromInput();
});

document.getElementById('trade-symbol').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') executeTrade();
});

document.getElementById('trade-shares').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') executeTrade();
});

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', function() {
    loadState();
    renderWatchlist();
    renderOrders();
    renderPortfolio();
    refreshWatchlistPrices();
    logToConsole('Welcome to Stock Predictor');
});
