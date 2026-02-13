"""Simple CLI for the A-share short-term decision skill."""

from __future__ import annotations

import argparse
import json
import os

from tools.fusion_engine import short_term_signal_engine
from tools.market_data import get_market_sentiment, get_sector_rotation, scan_strong_stocks
from tools.money_flow import analyze_capital_flow
from tools.reporting import generate_daily_report
from tools.risk_control import short_term_risk_control


def _print(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="A-share short-term decision tools")
    parser.add_argument(
        "tool",
        choices=[
            "get_market_sentiment",
            "get_sector_rotation",
            "scan_strong_stocks",
            "analyze_capital_flow",
            "short_term_signal_engine",
            "short_term_risk_control",
            "generate_daily_report",
        ],
    )
    parser.add_argument("--symbol", default=None, help="stock symbol for capital flow tool")
    parser.add_argument("--score", type=float, default=50, help="market sentiment score for risk control tool")
    parser.add_argument("--debug", action="store_true", help="enable debug_info in outputs")
    args = parser.parse_args()
    debug = bool(args.debug)
    if debug:
        os.environ["SHORT_DECISION_DEBUG"] = "1"

    if args.tool == "get_market_sentiment":
        _print(get_market_sentiment(debug=debug))
    elif args.tool == "get_sector_rotation":
        _print(get_sector_rotation(debug=debug))
    elif args.tool == "scan_strong_stocks":
        _print(scan_strong_stocks(debug=debug))
    elif args.tool == "analyze_capital_flow":
        _print(analyze_capital_flow(symbol=args.symbol, debug=debug))
    elif args.tool == "short_term_signal_engine":
        _print(short_term_signal_engine(debug=debug))
    elif args.tool == "short_term_risk_control":
        _print(short_term_risk_control(args.score))
    else:
        _print(generate_daily_report(debug=debug))


if __name__ == "__main__":
    main()
