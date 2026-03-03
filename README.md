```
██████╗ ███████╗████████╗██████╗  ██████╗
██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔═══██╗
██████╔╝█████╗     ██║   ██████╔╝██║   ██║
██╔══██╗██╔══╝     ██║   ██╔══██╗██║   ██║
██║  ██║███████╗   ██║   ██║  ██║╚██████╔╝
╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝

███████╗████████╗ ██████╗  ██████╗██╗  ██╗
██╔════╝╚══██╔══╝██╔═══██╗██╔════╝██║ ██╔╝
███████╗   ██║   ██║   ██║██║     █████╔╝
╚════██║   ██║   ██║   ██║██║     ██╔═██╗
███████║   ██║   ╚██████╔╝╚██████╗██║  ██╗
╚══════╝   ╚═╝    ╚═════╝  ╚═════╝╚═╝  ╚═╝

██████╗ ██████╗ ███████╗██████╗ ██╗ ██████╗████████╗ ██████╗ ██████╗
██╔══██╗██╔══██╗██╔════╝██╔══██╗██║██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
██████╔╝██████╔╝█████╗  ██║  ██║██║██║        ██║   ██║   ██║██████╔╝
██╔═══╝ ██╔══██╗██╔══╝  ██║  ██║██║██║        ██║   ██║   ██║██╔══██╗
██║     ██║  ██║███████╗██████╔╝██║╚██████╗   ██║   ╚██████╔╝██║  ██║
╚═╝     ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝
```

> *"The stock market is a device for transferring money from the impatient to the patient... and from the patient to the AI."* - Warren Buffett (probably)

---

## 🕹️ WHAT IS THIS THING?

Welcome to **RetroStockPredictor** - where Wall Street meets arcade machines.

This isn't your grandpa's stock ticker. This is a **hierarchical multi-agent AI system** that:
- Reads charts like a caffeinated day trader
- Sniffs out news sentiment like a conspiracy theorist with WiFi
- Crunches fundamentals like an accountant on Red Bull
- Makes predictions using ML that would make Skynet jealous

```
┌─────────────────────────────────────────────────────────┐
│                    🎮 AGENT HIERARCHY 🎮                 │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                      ┌─────────┐                        │
│                      │   CEO   │  <- Big brain energy   │
│                      │ 👔 🧠 💼 │                        │
│                      └────┬────┘                        │
│                           │                             │
│              ┌────────────┼────────────┐                │
│              ▼                         ▼                │
│        ┌──────────┐             ┌──────────┐            │
│        │  QUANT   │             │   RISK   │            │
│        │ 📊 🔢 📈 │             │ ⚠️ 🛡️ 🚨 │            │
│        └────┬─────┘             └──────────┘            │
│             │                                           │
│    ┌────────┼────────┬────────┐                         │
│    ▼        ▼        ▼        ▼                         │
│ ┌──────┐┌──────┐┌──────┐┌──────┐                        │
│ │TECH  ││FUNDA ││SENTI ││  ML  │  <- The worker bees    │
│ │📉    ││📋    ││😤    ││🤖    │                        │
│ └──────┘└──────┘└──────┘└──────┘                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 FEATURES

| Feature | Description | Vibe |
|---------|-------------|------|
| 📈 **Technical Analysis** | RSI, MACD, Bollinger Bands, Moving Averages | *lines go brrr* |
| 📰 **Sentiment Analysis** | News & social media mood detection | *are we feeling bullish today?* |
| 🧮 **Fundamental Analysis** | P/E ratios, earnings, the boring stuff | *spreadsheet gang* |
| 🤖 **ML Predictions** | Neural nets that dream of tendies | *beep boop buy AAPL* |
| 💼 **Paper Trading** | Practice mode so you don't YOLO your rent | *monopoly money* |
| 📊 **Backtesting** | See how badly you would've done in the past | *hindsight is 20/20* |

---

## ⚡ QUICK START

```bash
# Clone this bad boy
git clone https://github.com/Jack-Boop-Boop/RetroStockPredictor.git
cd RetroStockPredictor

# Install dependencies (grab a coffee)
pip install -r requirements.txt

# Set up your secrets
cp .env.example .env
# Edit .env with your API keys

# 🎮 PLAYER 1 READY
python main.py --analyze AAPL MSFT GOOGL

# Want to see how you'd do in the past?
python main.py --backtest --start 2024-01-01

# Feeling dangerous? (paper trading only, we're not animals)
python main.py --trade
```

---

## 🎰 HOW IT WORKS

```
          YOU                    THE MACHINE               STONKS
           │                          │                      │
           │   "analyze AAPL"         │                      │
           │─────────────────────────>│                      │
           │                          │                      │
           │                    ┌─────┴─────┐                │
           │                    │ FETCHING  │                │
           │                    │  DATA...  │                │
           │                    └─────┬─────┘                │
           │                          │                      │
           │                    ┌─────┴─────┐                │
           │                    │  AGENTS   │                │
           │                    │ THINKING  │                │
           │                    │    ...    │                │
           │                    └─────┬─────┘                │
           │                          │                      │
           │     BUY / SELL / HODL    │                      │
           │<─────────────────────────│                      │
           │                          │                      │
           │                          │      $$$             │
           │                          │─────────────────────>│
           │                          │                      │
           ▼                          ▼                      ▼
        😎📈                    🤖💹                    🚀🌕
```

---

## 📁 PROJECT STRUCTURE

```
RetroStockPredictor/
├── main.py              # 🎮 Start here, player one
├── config.yaml          # ⚙️ Tweak the knobs
├── requirements.txt     # 📦 The shopping list
│
├── src/
│   ├── agents/          # 🤖 The AI brain trust
│   │   ├── technical.py    # Chart wizard
│   │   ├── fundamental.py  # Numbers nerd
│   │   ├── sentiment.py    # Mood reader
│   │   ├── ml.py           # Robot overlord
│   │   ├── quant.py        # Strategy mastermind
│   │   ├── risk.py         # The adult in the room
│   │   └── ceo.py          # Big boss final decision
│   │
│   ├── data/            # 📊 Data wrangling
│   ├── execution/       # 💰 Trade execution
│   └── backtest/        # 🕐 Time machine
│
├── api/                 # 🌐 Web interface
└── web/                 # 🖥️ Frontend (if you're fancy)
```

---

## ⚠️ DISCLAIMER

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   THIS IS NOT FINANCIAL ADVICE.                               ║
║                                                               ║
║   This project is for EDUCATIONAL and ENTERTAINMENT           ║
║   purposes only. If you use this to trade real money          ║
║   and lose it all, that's on you, chief.                      ║
║                                                               ║
║   Past performance does not guarantee future results.         ║
║   The only guaranteed way to make money in the stock          ║
║   market is to sell courses about making money in the         ║
║   stock market.                                               ║
║                                                               ║
║   Invest responsibly. Or don't. I'm a README, not a cop.      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---


## Production Setup

### Prerequisites
- Python 3.11+
- PostgreSQL (or [Neon](https://neon.tech) / [Supabase](https://supabase.com) for serverless Postgres)
- Redis (optional, [Upstash](https://upstash.com) for caching + rate limiting)

### Environment Variables

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | Secret for signing auth tokens (32+ chars) |
| `REDIS_URL` | No | Redis URL for caching + rate limiting |
| `REDIS_TOKEN` | No | Redis auth token (Upstash) |
| `NEWS_API_KEY` | No | NewsAPI key for sentiment |
| `ALPHA_VANTAGE_KEY` | No | Alpha Vantage API key |
| `ENVIRONMENT` | No | `development` or `production` |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

Generate a JWT secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Install & Run

```bash
# Install dependencies
pip install -r requirements-local.txt

# Run database migrations
alembic upgrade head

# Seed demo user ($100k paper portfolio)
python -m scripts.seed

# Start the server
uvicorn src.api.app:app --reload --port 5000
```

Then open http://localhost:5000. Login with `demo@stockpredictor.local` / `changeme123`.

### API Documentation

In development mode, Swagger docs are available at http://localhost:5000/docs.

### Key API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/register` | POST | No | Create account |
| `/api/auth/login` | POST | No | Get JWT token |
| `/api/auth/me` | GET | Yes | Current user |
| `/api/portfolio` | GET | Yes | Portfolio summary with live P&L |
| `/api/portfolio/orders` | POST | Yes | Place a paper trade |
| `/api/portfolio/orders` | GET | Yes | Order history |
| `/api/analysis/run` | POST | Yes | Start analysis (background) |
| `/api/analysis/run/{id}` | GET | Yes | Poll analysis results |
| `/api/quote?symbol=AAPL` | GET | No | Real-time quote |
| `/api/watchlist` | GET | Yes | User's watchlist |
| `/api/health` | GET | No | Health check |

### Running Tests

```bash
python -m pytest tests/ -v
```

### Deploy Notes

- **Vercel**: The legacy `api/*.py` serverless endpoints still work for read-only quote/analyze. For full functionality (auth, trading, persistent state), deploy as a long-running process on Railway, Render, or Fly.io.
- **Database**: Use Neon or Supabase for serverless-friendly Postgres.
- **Redis**: Upstash provides a serverless Redis with a generous free tier.
- Set `ENVIRONMENT=production` to disable Swagger docs and enable generic error messages.

---

## CONTRIBUTING

Found a bug? Want to add a feature? Think you can beat the market?

1. Fork it 🍴
2. Branch it 🌿
3. Code it 💻
4. Push it 🚀
5. PR it 📬

---

## 📜 LICENSE

MIT License - Do whatever you want, just don't blame me when the robots take over.

---

<div align="center">

**Built with 💚 and questionable financial decisions**

*Remember: Bulls make money, bears make money, pigs get slaughtered, and AI just watches.*

```
   $$$$$$$
  $$$$$$$$$
 $$$$$$$$$$$
$$$$$  $$$$$
$$$     $$$$
$$$$$  $$$$$
 $$$$$$$$$$$
  $$$$$$$$$
   $$$$$$$
```

</div>
