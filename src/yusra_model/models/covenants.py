"""Covenant and financial health monitoring"""
from __future__ import annotations
from dataclasses import dataclass
from .loans import Portfolio
from .cashflow import CycleProjection
from ..config.loader import Config


@dataclass
class CovenantCheck:
    metric: str
    value: float
    value_str: str
    threshold: float
    threshold_str: str
    status: str  # "pass" | "warning" | "breach"


def check_dscr(portfolio: Portfolio, proj: CycleProjection) -> CovenantCheck:
    """Debt Service Coverage Ratio = Operating CF / Debt Service."""
    if not proj.rows:
        return CovenantCheck("DSCR", 0, "N/A", 1.2, "1.2x", "warning")

    q0 = proj.rows[0]
    op_cf = q0.sales_inflow - q0.overheads
    ds = q0.repayments
    if ds <= 0 or op_cf <= 0:
        return CovenantCheck("DSCR (Q1)", 0, "N/A", 1.2, "1.2x", "warning")

    ratio = op_cf / ds
    val_str = f"{ratio:.2f}x"
    if ratio >= 1.5:
        status = "pass"
    elif ratio >= 1.2:
        status = "warning"
    else:
        status = "breach"
    return CovenantCheck("DSCR (Q1)", ratio, val_str, 1.2, "1.2x", status)


def check_utilization(portfolio: Portfolio, proj: CycleProjection) -> CovenantCheck:
    """Worst facility utilization across all quarters."""
    results = []
    for row in proj.rows:
        util = row.facility_util_pct
        pct = util * 100
        val_str = f"{pct:.1f}%"
        if util < 0.80:
            status = "pass"
        elif util < 0.95:
            status = "warning"
        else:
            status = "breach"
        results.append(CovenantCheck(
            f"Utilization ({row.quarter})", util, val_str, 0.80, "80%", status))
    worst_val = max(r.value for r in results)
    worst = next(r for r in results if r.value == worst_val)
    return worst


def check_liquidity(cfg: Config, proj: CycleProjection) -> CovenantCheck:
    """Minimum cash buffer check."""
    min_buffer = cfg.overheads_per_month * 3
    min_buffer_str = f"ETB {min_buffer:,.0f}"
    worst = proj.rows[-1] if proj.rows else None
    if not worst:
        return CovenantCheck("Min Cash Buffer", 0, "N/A", min_buffer, min_buffer_str, "warning")
    closing = worst.closing_cash
    val_str = f"ETB {closing:,.0f}"
    if closing >= min_buffer * 2:
        status = "pass"
    elif closing >= min_buffer:
        status = "warning"
    else:
        status = "breach"
    return CovenantCheck(f"Closing Cash ({worst.quarter})", closing, val_str,
                         min_buffer, min_buffer_str, status)


def check_current_ratio(portfolio: Portfolio, proj: CycleProjection) -> CovenantCheck:
    """Current ratio = current assets / current liabilities."""
    if not proj.rows:
        return CovenantCheck("Current Ratio", 0, "N/A", 1.5, "1.5x", "warning")
    row = proj.rows[0]
    current_assets = row.opening_cash + row.closing_inventory
    current_liabs = portfolio.total_quarterly_repayment
    if current_liabs <= 0:
        return CovenantCheck("Current Ratio", 0, "N/A", 1.5, "1.5x", "warning")
    ratio = current_assets / current_liabs
    val_str = f"{ratio:.2f}x"
    if ratio >= 2.0:
        status = "pass"
    elif ratio >= 1.5:
        status = "warning"
    else:
        status = "breach"
    return CovenantCheck("Current Ratio (Q1)", ratio, val_str, 1.5, "1.5x", status)


def check_all(portfolio: Portfolio, proj: CycleProjection, cfg: Config) -> list[CovenantCheck]:
    """Run all covenant checks and return results."""
    return [
        check_dscr(portfolio, proj),
        check_utilization(portfolio, proj),
        check_liquidity(cfg, proj),
        check_current_ratio(portfolio, proj),
    ]
