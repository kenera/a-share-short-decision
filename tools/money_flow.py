"""Capital flow analysis tools."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Any, Dict

from .debug_utils import resolve_debug, with_debug

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None  # type: ignore


def _to_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or pd is None:
        return []
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    return frame.to_dict(orient="records")


def _num(row: dict[str, Any], keys: list[str], default: float = 0.0) -> float:
    for key in keys:
        if key in row and row[key] not in ("", None):
            try:
                return float(row[key])
            except Exception:
                continue
    return default


def _normalize_number(value: Any) -> float:
    if value in ("", None):
        return 0.0
    if isinstance(value, (int, float)):
        out = float(value)
        return out if math.isfinite(out) else 0.0
    text = str(value).strip().replace(",", "")
    if text in ("-", "--"):
        return 0.0
    unit = 1.0
    if text.endswith("亿"):
        unit = 100_000_000.0
        text = text[:-1]
    elif text.endswith("万"):
        unit = 10_000.0
        text = text[:-1]
    try:
        out = float(text) * unit
        return out if math.isfinite(out) else 0.0
    except Exception:
        return 0.0


def _num_unit(row: dict[str, Any], keys: list[str], default: float = 0.0) -> float:
    for key in keys:
        if key in row:
            parsed = _normalize_number(row[key])
            if parsed != 0.0 or row[key] in (0, "0", "0.0"):
                return parsed
    return default


def _fallback_capital_flow(
    symbol: str | None = None, debug: bool = False, debug_info: dict[str, Any] | None = None
) -> Dict[str, Any]:
    payload = {
        "symbol": symbol or "market",
        "main_flow": 180_000_000,
        "northbound_net": 530_000_000,
        "northbound_inflow_days": 3,
        "flow_trend": "3-day-inflow",
        "strength_rank": 12,
        "data_source": "fallback",
    }
    return with_debug(payload, debug, debug_info or {"reason": "fallback_default_capital_flow"})


def _count_consecutive_inflow(values: list[float]) -> int:
    count = 0
    for item in reversed(values):
        if item > 0:
            count += 1
        else:
            break
    return count


def _load_northbound_series(debug_info: dict[str, Any] | None = None) -> list[float]:
    if ak is None or pd is None:
        return []

    # Priority 1: explicit northbound net flow endpoint
    try:
        flow_df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        flow_records = _to_records(flow_df)
        if debug_info is not None:
            debug_info.setdefault("api_calls", []).append(
                {"api": "stock_hsgt_north_net_flow_in_em", "ok": True, "rows": len(flow_records)}
            )
        vals = [_num_unit(x, ["value", "净流入", "当日净流入", "净买额"], 0.0) for x in flow_records]
        vals = [x for x in vals if x != 0.0]
        if vals:
            return vals[-20:]
    except Exception:
        if debug_info is not None:
            debug_info.setdefault("api_calls", []).append({"api": "stock_hsgt_north_net_flow_in_em", "ok": False})

    # Priority 2: historical HSGT statistics
    if hasattr(ak, "stock_hsgt_hist_em"):
        for symbol in ("北向资金", "沪股通", "深股通"):
            try:
                hist_df = ak.stock_hsgt_hist_em(symbol=symbol)
                hist_records = _to_records(hist_df)
                if debug_info is not None:
                    debug_info.setdefault("api_calls", []).append(
                        {"api": "stock_hsgt_hist_em", "symbol": symbol, "ok": True, "rows": len(hist_records)}
                    )
                vals = [_num_unit(x, ["当日成交净买额", "当日净流入", "净买额", "净流入"], 0.0) for x in hist_records]
                vals = [x for x in vals if x != 0.0]
                if vals:
                    return vals[-20:]
            except Exception:
                if debug_info is not None:
                    debug_info.setdefault("api_calls", []).append({"api": "stock_hsgt_hist_em", "symbol": symbol, "ok": False})
                continue
    return []


def _load_symbol_main_flow(symbol: str, debug_info: dict[str, Any] | None = None) -> float:
    if ak is None or pd is None:
        return 0.0

    # Priority 1: per-stock historical money flow
    try:
        start = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        end = datetime.now().strftime("%Y%m%d")
        hist = ak.stock_individual_fund_flow(symbol=symbol, start_date=start, end_date=end)
        records = _to_records(hist)
        if debug_info is not None:
            debug_info.setdefault("api_calls", []).append(
                {"api": "stock_individual_fund_flow", "symbol": symbol, "ok": True, "rows": len(records)}
            )
        if records:
            latest = records[-1]
            return _num_unit(latest, ["主力净流入-净额", "主力净额", "主力净流入", "主力净流入净额"], 0.0)
    except Exception:
        if debug_info is not None:
            debug_info.setdefault("api_calls", []).append({"api": "stock_individual_fund_flow", "symbol": symbol, "ok": False})

    # Priority 2: ranking table snapshot
    if hasattr(ak, "stock_individual_fund_flow_rank"):
        for indicator in ("今日", "5日", "10日"):
            try:
                rank_df = ak.stock_individual_fund_flow_rank(indicator=indicator)
                rows = _to_records(rank_df)
                if debug_info is not None:
                    debug_info.setdefault("api_calls", []).append(
                        {
                            "api": "stock_individual_fund_flow_rank",
                            "indicator": indicator,
                            "ok": True,
                            "rows": len(rows),
                        }
                    )
                for row in rows:
                    code = str(row.get("股票代码", row.get("代码", ""))).strip()
                    if code == symbol:
                        return _num_unit(row, ["今日主力净流入-净额", "主力净流入-净额", "主力净额"], 0.0)
            except Exception:
                if debug_info is not None:
                    debug_info.setdefault("api_calls", []).append(
                        {"api": "stock_individual_fund_flow_rank", "indicator": indicator, "ok": False}
                    )
                continue
    return 0.0


def analyze_capital_flow(symbol: str | None = None, debug: bool = False) -> Dict[str, Any]:
    """
    Analyze capital flow for a symbol or whole market.

    If symbol is None, return market-level flow proxy.
    """
    debug = resolve_debug(debug)
    dbg: dict[str, Any] = {"module": "analyze_capital_flow", "symbol": symbol or "market", "api_calls": []}
    if ak is None or pd is None:
        dbg["fallback_reason"] = "akshare_or_pandas_missing"
        return _fallback_capital_flow(symbol, debug=debug, debug_info=dbg)

    north_vals = _load_northbound_series(debug_info=dbg)
    if not north_vals:
        dbg["fallback_reason"] = "northbound_series_empty"
        return _fallback_capital_flow(symbol, debug=debug, debug_info=dbg)

    northbound_net = north_vals[-1]
    northbound_inflow_days = _count_consecutive_inflow(north_vals)

    main_flow = _load_symbol_main_flow(symbol, debug_info=dbg) if symbol else northbound_net * 0.55

    if main_flow >= 300_000_000:
        strength_rank = 5
    elif main_flow >= 150_000_000:
        strength_rank = 12
    elif main_flow >= 0:
        strength_rank = 30
    else:
        strength_rank = 70

    trend = f"{northbound_inflow_days}-day-inflow" if northbound_inflow_days > 0 else "outflow"
    payload = {
        "symbol": symbol or "market",
        "main_flow": int(main_flow),
        "northbound_net": int(northbound_net),
        "northbound_inflow_days": northbound_inflow_days,
        "flow_trend": trend,
        "strength_rank": strength_rank,
        "data_source": "akshare-live",
    }
    dbg["derived"] = {"north_series_points": len(north_vals)}
    return with_debug(payload, debug, dbg)
