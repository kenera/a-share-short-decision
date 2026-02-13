---
name: a-share-short-decision
description: A-share short-term trading decision skill for 1-5 day horizon. Use when you need market sentiment, sector rotation, strong stock scanning, capital flow confirmation, weighted short-term signal scoring, strict risk-control filtering, and daily report generation for CN A-share momentum trading.
---

# A-Share Short-Term Decision Skill

Implement short-term decision in this sequence:

1. Run `get_market_sentiment`.
2. Run `get_sector_rotation`.
3. Run `scan_strong_stocks` with selected sectors.
4. Run `analyze_capital_flow` for top candidate.
5. Run `short_term_signal_engine`.
6. Apply `short_term_risk_control`.
7. Output daily summary with `generate_daily_report`.

## Tool Contracts

### `get_market_sentiment()`

Return:

```json
{
  "limit_up": 65,
  "limit_down": 4,
  "max_height": 4,
  "break_rate": 0.18,
  "market_sentiment_score": 72
}
```

### `get_sector_rotation(top_n=5)`

Return:

```json
{
  "top_sectors": [
    {"name": "AI-Compute", "strength": 85.2}
  ]
}
```

### `scan_strong_stocks(sectors=None, top_n=10)`

Filtering rules:
- daily change > 5%
- volume ratio > 1.5
- 3-day up trend
- exclude high-volume bearish candle

### `analyze_capital_flow(symbol=None)`

Return:

```json
{
  "main_flow": 180000000,
  "flow_trend": "3-day-inflow"
}
```

### `short_term_signal_engine()`

Weights:
- market sentiment 25%
- sector strength 25%
- stock volume strength 20%
- capital inflow 20%
- technical structure 10%

Signal policy:
- score >= 75: `SHORT_BUY`
- 60~75: `WATCHLIST`
- <60: `NO_TRADE`

### `short_term_risk_control(market_sentiment_score)`

Rules:
- max position <= 15%
- -6% hard stop
- block new entries when sentiment < 40

### `generate_daily_report()`

Output daily text report with:
- market sentiment
- strongest sectors
- short-term focus stocks
- risk and execution guidance

## Runtime

Run tools via:

```bash
python main.py short_term_signal_engine
python main.py generate_daily_report
```
