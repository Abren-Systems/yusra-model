"""Financial ratios and KPI calculations"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class FinancialRatios:
    dscr: float | str = "N/A"
    current_ratio: float = 0.0
    quick_ratio: float = 0.0
    dso_days: float = 30.0
    dio_days: float = 0.0
    inventory_turnover: float = 0.0
    cash_conversion_cycle: float = 0.0


def calculate_ratios(
    opening_cash: float,
    opening_inventory: float,
    total_facility: float,
    gross_profit_margin: float,
    quarterly_sales: float,
    quarterly_repayments: float,
    quarterly_overheads: float,
    sales_cycle: str,
) -> FinancialRatios:
    r = FinancialRatios()

    # DSCR
    op_cf = quarterly_sales - quarterly_overheads
    debt_service = quarterly_repayments
    if debt_service > 0 and op_cf > 0:
        r.dscr = round(op_cf / debt_service, 2)
    else:
        r.dscr = "N/A"

    # Current / Quick ratio
    total_current_assets = opening_cash + opening_inventory
    total_current_liabs = opening_inventory  # simplified: payables ~ inventory
    r.current_ratio = round(total_current_assets / total_current_liabs, 2) if total_current_liabs else 0
    r.quick_ratio = round(opening_cash / total_current_liabs, 2) if total_current_liabs else 0

    # DIO
    cogs = quarterly_sales / (1 + gross_profit_margin) if gross_profit_margin > 0 else quarterly_sales
    daily_cogs = cogs / 90 if cogs > 0 else 1
    r.dio_days = round(opening_inventory / daily_cogs, 1) if cogs > 0 else 0

    # Inventory turnover
    r.inventory_turnover = 4.0 if sales_cycle == "3 Months" else 2.0

    # Cash conversion cycle
    r.cash_conversion_cycle = r.dso_days + r.dio_days - 30.0  # assume DPO = 30

    return r


def recycling_kpis(
    total_facility: float,
    total_principal: float,
    cumulative_throughput: float,
    ceo_target: float,
) -> dict:
    return {
        "total_initial_throughput": total_principal,
        "recycling_potential": round(total_facility - total_principal + total_principal, 2),
        "cumulative_throughput": cumulative_throughput,
        "throughput_target": ceo_target,
        "recycle_efficiency": round(cumulative_throughput / total_facility, 2) if total_facility else 0,
        "gap_to_ceo_target": round(max(0, ceo_target - cumulative_throughput), 2),
    }
