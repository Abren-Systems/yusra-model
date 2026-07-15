"""Excel workbook orchestrator"""
from __future__ import annotations
from pathlib import Path
import openpyxl
from yusra_model.config.loader import Config
from yusra_model.models.loans import Portfolio
from yusra_model.models.cashflow import CashFlowProjection, CycleProjection
from yusra_model.output.sheets import inputs, schedule, projection, dashboard, strategy


def build_workbook(
    cfg: Config,
    portfolio: Portfolio,
    proj: CashFlowProjection,
    active_proj: CycleProjection,
    audit: dict | None = None,
    output_path: str | Path = "./reports/YUSRA_PHARMA_Financial_Model.xlsx",
) -> str:
    """Build the full 6-sheet Excel workbook (inputs + 5 computed sheets)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()

    inputs.build(wb.active, cfg, portfolio, audit=audit)
    schedule.build(wb.create_sheet(), cfg, portfolio)
    projection.build(wb.create_sheet(), cfg, portfolio, proj, active_proj)
    dashboard.build(wb.create_sheet(), cfg, portfolio, proj, active_proj)
    strategy.build(wb.create_sheet(), cfg, portfolio)

    wb.save(str(output_path))
    return str(output_path)
