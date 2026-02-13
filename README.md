# a-share-short-decision

OpenClaw skill implementation for A-share short-term (1-5 day) decision support.

## Structure

```text
a-share-short-decision/
├── tools/
│   ├── __init__.py
│   ├── market_data.py
│   ├── indicators.py
│   ├── sentiment.py
│   ├── money_flow.py
│   ├── fusion_engine.py
│   ├── risk_control.py
│   └── reporting.py
├── prompts/
│   └── analysis_prompt.txt
├── scheduler.yaml
├── config.json
├── main.py
├── SKILL.md
└── README.md
```

## Tools

- `get_market_sentiment`: market sentiment from limit-up/limit-down stats
- `get_sector_rotation`: strongest sectors by price/turnover/leadership strength
- `scan_strong_stocks`: candidate scan based on momentum + volume expansion
- `analyze_capital_flow`: main-force and northbound capital trend
- `short_term_signal_engine`: weighted score engine (0-100) and action signal
- `short_term_risk_control`: strict short-term risk constraints
- `generate_daily_report`: daily push text in report format

## Install

```bash
pip install akshare pandas
```

If `akshare` data is unavailable, built-in fallback data keeps tools runnable.

## Run

```bash
python main.py get_market_sentiment
python main.py get_sector_rotation
python main.py scan_strong_stocks
python main.py analyze_capital_flow --symbol 300750
python main.py short_term_signal_engine
python main.py short_term_risk_control --score 72
python main.py generate_daily_report
python main.py short_term_signal_engine --debug
```

Or enable globally:

```bash
set SHORT_DECISION_DEBUG=1
python main.py short_term_signal_engine
```

## Strategy Rules

- Weight:
  - market sentiment 25%
  - sector strength 25%
  - stock volume strength 20%
  - capital inflow 20%
  - technical structure 10%
- Signal:
  - `score >= 75`: `SHORT_BUY`
  - `60 <= score < 75`: `WATCHLIST`
  - `score < 60`: `NO_TRADE`
- Risk:
  - max single position `<= 15%`
  - stop loss `-6%`
  - sentiment score `< 40`: no new positions
