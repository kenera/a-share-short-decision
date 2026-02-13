"""Market data access and stock scanning tools for short-term strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import re
from typing import Any, Dict, List

from .debug_utils import resolve_debug, with_debug
from .indicators import clamp, trend_up, volume_ratio

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None  # type: ignore

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None  # type: ignore


@dataclass
class StockCandidate:
    code: str
    name: str
    change_pct: float
    volume_ratio: float
    strength_rank: int
    sector: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "change_pct": round(self.change_pct, 2),
            "volume_ratio": round(self.volume_ratio, 2),
            "strength_rank": self.strength_rank,
            "sector": self.sector,
        }


def _to_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if pd is None:
        return []
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    return frame.to_dict(orient="records")


def _num(row: dict[str, Any], keys: list[str], default: float = 0.0) -> float:
    for key in keys:
        if key in row and row[key] is not None and row[key] != "":
            try:
                return float(row[key])
            except Exception:
                continue
    return default


def _str(row: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key]).strip()
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


def _parse_board_height(raw: Any) -> int:
    if raw in ("", None):
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw).strip()
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else 0


def _recent_trade_dates(days: int = 10) -> list[str]:
    today = datetime.now().date()
    dates: list[str] = []
    for offset in range(days):
        d = today - timedelta(days=offset)
        if d.weekday() < 5:
            dates.append(d.strftime("%Y%m%d"))
    return dates


def _fallback_market_sentiment(debug: bool = False, debug_info: dict[str, Any] | None = None) -> dict[str, Any]:
    limit_up = 42
    limit_down = 9
    max_height = 3
    break_rate = 0.21
    turnover = 980_000_000_000
    score = (
        clamp(limit_up / 70 * 45, 0, 45)
        + clamp((12 - limit_down) / 12 * 20, 0, 20)
        + clamp(max_height / 6 * 20, 0, 20)
        + clamp((0.35 - break_rate) / 0.35 * 15, 0, 15)
    )
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "limit_up": limit_up,
        "limit_down": limit_down,
        "max_height": max_height,
        "break_rate": round(break_rate, 4),
        "turnover": turnover,
        "market_sentiment_score": round(score, 2),
        "data_source": "fallback",
    }
    return with_debug(payload, debug, debug_info or {"reason": "fallback_default_values"})


def get_market_sentiment(debug: bool = False) -> dict[str, Any]:
    """
    Compute market sentiment score based on limit-up/down behavior.

    Returns keys:
    - limit_up, limit_down, max_height, break_rate, turnover, market_sentiment_score
    """
    debug = resolve_debug(debug)
    dbg: dict[str, Any] = {"module": "get_market_sentiment", "akshare_available": ak is not None, "pandas_available": pd is not None}
    if ak is None or pd is None:
        dbg["fallback_reason"] = "akshare_or_pandas_missing"
        return _fallback_market_sentiment(debug=debug, debug_info=dbg)

    chosen_date = ""
    zt_records: list[dict[str, Any]] = []
    dt_records: list[dict[str, Any]] = []
    zb_records: list[dict[str, Any]] = []

    dbg["date_candidates"] = _recent_trade_dates()
    dbg["api_calls"] = []
    for date_text in _recent_trade_dates():
        try:
            zt_df = ak.stock_zt_pool_em(date=date_text)
            dbg["api_calls"].append({"api": "stock_zt_pool_em", "date": date_text, "ok": True})
            records = _to_records(zt_df)
            if records:
                chosen_date = date_text
                zt_records = records
                break
        except Exception:
            dbg["api_calls"].append({"api": "stock_zt_pool_em", "date": date_text, "ok": False})
            continue

    if not zt_records:
        dbg["fallback_reason"] = "empty_limit_up_pool"
        return _fallback_market_sentiment(debug=debug, debug_info=dbg)

    if not chosen_date:
        chosen_date = datetime.now().strftime("%Y%m%d")

    try:
        dt_records = _to_records(ak.stock_zt_pool_dtgc_em(date=chosen_date))
        dbg["api_calls"].append({"api": "stock_zt_pool_dtgc_em", "date": chosen_date, "ok": True, "rows": len(dt_records)})
    except Exception:
        dt_records = []
        dbg["api_calls"].append({"api": "stock_zt_pool_dtgc_em", "date": chosen_date, "ok": False})

    try:
        if hasattr(ak, "stock_zt_pool_zbgc_em"):
            zb_records = _to_records(ak.stock_zt_pool_zbgc_em(date=chosen_date))
            dbg["api_calls"].append({"api": "stock_zt_pool_zbgc_em", "date": chosen_date, "ok": True, "rows": len(zb_records)})
    except Exception:
        zb_records = []
        dbg["api_calls"].append({"api": "stock_zt_pool_zbgc_em", "date": chosen_date, "ok": False})

    limit_up = len(zt_records)
    limit_down = len(dt_records)
    max_height = 0

    for row in zt_records:
        height = _parse_board_height(_str(row, ["连板数", "连板", "连板高度", "几天几板"], "1"))
        max_height = max(max_height, height)

    break_count = len(zb_records)
    if break_count == 0:
        # fallback: derive from state flags in limit-up pool
        for row in zt_records:
            state = _str(row, ["状态", "涨停状态", "封板状态"], "")
            if state and state not in ("封板", "涨停"):
                break_count += 1

    total_lu_events = limit_up + break_count
    break_rate = break_count / total_lu_events if total_lu_events else 0.0

    turnover = 0.0
    try:
        spot_records = _to_records(ak.stock_zh_a_spot_em())
        dbg["api_calls"].append({"api": "stock_zh_a_spot_em", "ok": True, "rows": len(spot_records)})
        for row in spot_records:
            turnover += _num_unit(row, ["成交额", "成交额(元)", "amount"], 0.0)
    except Exception:
        turnover = 0.0
        dbg["api_calls"].append({"api": "stock_zh_a_spot_em", "ok": False})

    score = (
        clamp(limit_up / 70 * 45, 0, 45)
        + clamp((12 - limit_down) / 12 * 20, 0, 20)
        + clamp(max_height / 6 * 20, 0, 20)
        + clamp((0.35 - break_rate) / 0.35 * 15, 0, 15)
    )

    payload = {
        "date": f"{chosen_date[:4]}-{chosen_date[4:6]}-{chosen_date[6:8]}",
        "limit_up": limit_up,
        "limit_down": limit_down,
        "max_height": max_height,
        "break_rate": round(break_rate, 4),
        "turnover": int(turnover),
        "market_sentiment_score": round(score, 2),
        "data_source": "akshare-live",
    }
    dbg["derived"] = {"break_count": break_count, "total_lu_events": total_lu_events}
    return with_debug(payload, debug, dbg)


def _fallback_sector_rotation(debug: bool = False, debug_info: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "top_sectors": [
            {"name": "AI-Compute", "change_pct": 4.2, "turnover": 62_000_000_000, "limit_up_count": 7, "strength": 85.2},
            {"name": "Semiconductor", "change_pct": 3.6, "turnover": 58_000_000_000, "limit_up_count": 5, "strength": 79.8},
            {"name": "Robotics", "change_pct": 2.9, "turnover": 44_000_000_000, "limit_up_count": 4, "strength": 72.3},
        ],
        "data_source": "fallback",
    }
    return with_debug(payload, debug, debug_info or {"reason": "fallback_default_sectors"})


def get_sector_rotation(top_n: int = 5, debug: bool = False) -> dict[str, Any]:
    """Return top sectors by weighted short-term strength."""
    debug = resolve_debug(debug)
    dbg: dict[str, Any] = {"module": "get_sector_rotation", "api_calls": []}
    if ak is None or pd is None:
        dbg["fallback_reason"] = "akshare_or_pandas_missing"
        return _fallback_sector_rotation(debug=debug, debug_info=dbg)

    sector_rows: list[dict[str, Any]] = []
    try:
        sector_rows = _to_records(ak.stock_board_industry_name_em())
        dbg["api_calls"].append({"api": "stock_board_industry_name_em", "ok": True, "rows": len(sector_rows)})
    except Exception:
        sector_rows = []
        dbg["api_calls"].append({"api": "stock_board_industry_name_em", "ok": False})

    if not sector_rows and hasattr(ak, "stock_board_concept_name_em"):
        try:
            sector_rows = _to_records(ak.stock_board_concept_name_em())
            dbg["api_calls"].append({"api": "stock_board_concept_name_em", "ok": True, "rows": len(sector_rows)})
        except Exception:
            sector_rows = []
            dbg["api_calls"].append({"api": "stock_board_concept_name_em", "ok": False})

    if not sector_rows:
        dbg["fallback_reason"] = "no_sector_rows"
        return _fallback_sector_rotation(debug=debug, debug_info=dbg)

    sectors: list[dict[str, Any]] = []
    max_turnover = max(_num_unit(row, ["成交额", "总成交额", "总市值"], 0.0) for row in sector_rows) or 1.0

    for row in sector_rows:
        name = _str(row, ["板块名称", "名称"], "UNKNOWN")
        change_pct = _num(row, ["涨跌幅", "涨跌幅%"], 0.0)
        turnover = _num_unit(row, ["成交额", "总成交额", "总市值"], 0.0)
        up_count = int(_num(row, ["上涨家数"], 0.0))
        limit_up_count = int(_num(row, ["涨停家数"], 0.0))
        if limit_up_count == 0 and up_count > 0:
            limit_up_count = int(up_count * 0.08)

        strength = (
            clamp(change_pct / 7 * 45, 0, 45)
            + clamp(turnover / max_turnover * 25, 0, 25)
            + clamp(limit_up_count / 12 * 30, 0, 30)
        )

        sectors.append(
            {
                "name": name,
                "change_pct": round(change_pct, 2),
                "turnover": int(turnover),
                "limit_up_count": limit_up_count,
                "board_code": _str(row, ["板块代码", "代码"], ""),
                "strength": round(strength, 2),
            }
        )

    sectors.sort(key=lambda x: x["strength"], reverse=True)
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "top_sectors": sectors[:top_n],
        "data_source": "akshare-live",
    }
    dbg["derived"] = {"input_rows": len(sector_rows), "returned_rows": min(top_n, len(sectors))}
    return with_debug(payload, debug, dbg)


def _fallback_scan_strong_stocks(
    sectors: list[str] | None = None, top_n: int = 10, debug: bool = False, debug_info: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    base = [
        StockCandidate("300001", "DemoTech", 8.1, 2.4, 1, "AI-Compute").to_dict(),
        StockCandidate("002345", "ChipStar", 6.8, 1.9, 2, "Semiconductor").to_dict(),
        StockCandidate("688888", "RoboCore", 5.5, 1.7, 3, "Robotics").to_dict(),
    ]
    if sectors:
        filt = [x for x in base if x["sector"] in sectors]
        out = filt[:top_n] if filt else base[:top_n]
    else:
        out = base[:top_n]
    if not debug:
        return out
    return [dict(item, debug_info=debug_info or {"reason": "fallback_default_candidates"}) for item in out]


def scan_strong_stocks(sectors: list[str] | None = None, top_n: int = 10, debug: bool = False) -> list[dict[str, Any]]:
    """
    Scan candidate stocks from strong sectors.

    Rules:
    - today's change > 5%
    - volume ratio > 1.5
    - 3-day trend up
    - avoid high-volume bearish pattern
    """
    debug = resolve_debug(debug)
    dbg: dict[str, Any] = {"module": "scan_strong_stocks", "api_calls": [], "sectors_filter": sectors or []}
    if ak is None or pd is None:
        dbg["fallback_reason"] = "akshare_or_pandas_missing"
        return _fallback_scan_strong_stocks(sectors, top_n, debug=debug, debug_info=dbg)

    try:
        spot_df = ak.stock_zh_a_spot_em()
        dbg["api_calls"].append({"api": "stock_zh_a_spot_em", "ok": True})
    except Exception:
        dbg["api_calls"].append({"api": "stock_zh_a_spot_em", "ok": False})
        dbg["fallback_reason"] = "spot_api_failed"
        return _fallback_scan_strong_stocks(sectors, top_n, debug=debug, debug_info=dbg)

    rows = _to_records(spot_df)
    if not rows:
        dbg["fallback_reason"] = "spot_rows_empty"
        return _fallback_scan_strong_stocks(sectors, top_n, debug=debug, debug_info=dbg)

    allowed_codes: set[str] | None = None
    if sectors:
        allowed_codes = set()
        for sector_name in sectors:
            try:
                if hasattr(ak, "stock_board_industry_cons_em"):
                    cons_df = ak.stock_board_industry_cons_em(symbol=sector_name)
                    dbg["api_calls"].append({"api": "stock_board_industry_cons_em", "symbol": sector_name, "ok": True})
                    for record in _to_records(cons_df):
                        code = _str(record, ["代码", "股票代码"], "")
                        if code:
                            allowed_codes.add(code)
                elif hasattr(ak, "stock_board_concept_cons_em"):
                    cons_df = ak.stock_board_concept_cons_em(symbol=sector_name)
                    dbg["api_calls"].append({"api": "stock_board_concept_cons_em", "symbol": sector_name, "ok": True})
                    for record in _to_records(cons_df):
                        code = _str(record, ["代码", "股票代码"], "")
                        if code:
                            allowed_codes.add(code)
            except Exception:
                dbg["api_calls"].append({"api": "board_cons", "symbol": sector_name, "ok": False})
                continue
        if not allowed_codes:
            allowed_codes = None

    pre_filtered = []
    for row in rows:
        code = _str(row, ["代码", "股票代码"], "")
        change_pct = _num(row, ["涨跌幅"], 0.0)
        if change_pct > 4.5:
            if allowed_codes is None or code in allowed_codes:
                pre_filtered.append(row)

    pre_filtered.sort(key=lambda x: _num(x, ["涨跌幅"], 0.0), reverse=True)
    universe = pre_filtered[:120]

    candidates: list[StockCandidate] = []
    for row in universe:
        code = _str(row, ["代码", "股票代码"], "")
        name = _str(row, ["名称", "股票名称"], "")
        change_pct = _num(row, ["涨跌幅"], 0.0)
        turnover_rate = _num(row, ["量比"], 0.0)
        sector = _str(row, ["所处行业", "行业"], "UNKNOWN")

        if change_pct <= 5:
            continue
        if turnover_rate <= 1.5:
            continue
        if allowed_codes is not None and code not in allowed_codes:
            continue

        try:
            start_date = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
            hist = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq",
            )
        except Exception:
            dbg["api_calls"].append({"api": "stock_zh_a_hist", "symbol": code, "ok": False})
            continue

        records = _to_records(hist)
        if len(records) < 5:
            continue

        closes = [_num(x, ["收盘"], 0.0) for x in records]
        opens = [_num(x, ["开盘"], 0.0) for x in records]
        volumes = [_num(x, ["成交量"], 0.0) for x in records]

        if not trend_up(closes, lookback=3):
            continue

        baseline = sum(volumes[-6:-1]) / max(len(volumes[-6:-1]), 1)
        vol_ratio = volume_ratio(volumes[-1], baseline)
        if vol_ratio <= 1.5:
            continue

        last_day_change = ((closes[-1] - closes[-2]) / closes[-2] * 100) if closes[-2] else 0.0
        high_volume_bearish = (opens[-1] > closes[-1] and last_day_change < -2.0 and vol_ratio > 2.2)
        if high_volume_bearish:
            continue

        candidates.append(
            StockCandidate(
                code=code,
                name=name,
                change_pct=change_pct,
                volume_ratio=vol_ratio,
                strength_rank=0,
                sector=sector,
            )
        )

    candidates.sort(key=lambda x: (x.change_pct, x.volume_ratio), reverse=True)
    ranked: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates[:top_n], start=1):
        item.strength_rank = idx
        ranked.append(item.to_dict())
    if not debug:
        return ranked
    dbg["derived"] = {
        "spot_rows": len(rows),
        "pre_filtered": len(pre_filtered),
        "universe": len(universe),
        "candidates": len(ranked),
    }
    return [dict(item, debug_info=dbg) for item in ranked]
