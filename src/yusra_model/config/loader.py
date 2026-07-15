"""Configuration loader — YAML or Excel input template"""
from __future__ import annotations
import yaml
import json
from pathlib import Path
from jsonschema import validate as json_validate, ValidationError
from typing import Any
from dataclasses import dataclass
from datetime import date


@dataclass
class Config:
    """Normalised configuration object after loading."""
    company: str
    currency: str
    opening_cash: float
    opening_inventory: float
    total_facility: float
    overheads_per_month: float
    profit_rate: float
    loan_tenor_quarters: int
    baseline_rate: float
    stress_rate: float
    sales_cycle_options: list[str]
    cash_ratio: float
    credit_ratio: float
    gross_profit_margin: float
    loans: list[dict]
    ceo_throughput_target: float
    plan_throughput_target: float
    min_sales_buffer: float


def load_config(path: str | Path) -> Config:
    """Load YAML config, validate against schema, return normalised Config."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    schema_path = Path(__file__).parent.parent.parent.parent / "config" / "schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    try:
        json_validate(raw, schema)
    except ValidationError as e:
        raise ValueError(f"Config validation error: {e.message}") from e

    p = raw["parameters"]
    ex = raw["exchanges"]
    s = raw["sales"]
    t = raw["targets"]

    loans = []
    for loan in raw["loans"]:
        l = dict(loan)
        l["start_date"] = date.fromisoformat(l["start_date"])
        loans.append(l)

    return Config(
        company=raw["company"],
        currency=raw["currency"],
        opening_cash=float(p["opening_cash"]),
        opening_inventory=float(p["opening_inventory"]),
        total_facility=float(p["total_facility"]),
        overheads_per_month=float(p["overheads_per_month"]),
        profit_rate=float(p["profit_rate"]),
        loan_tenor_quarters=int(p["loan_tenor_quarters"]),
        baseline_rate=float(ex["baseline"]),
        stress_rate=float(ex["stress"]),
        sales_cycle_options=list(s["cycle_options"]),
        cash_ratio=float(s["cash_ratio"]),
        credit_ratio=float(s["credit_ratio"]),
        gross_profit_margin=float(s["gross_profit_margin"]),
        loans=loans,
        ceo_throughput_target=float(t.get("ceo_throughput", 240000000)),
        plan_throughput_target=float(t.get("plan_throughput", 140000000)),
        min_sales_buffer=float(t.get("min_sales_buffer", 500000)),
    )


def generate_input_template(path: str | Path) -> None:
    """Generate a blank Excel input template for non-technical users."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inputs"

    hdr_font = Font(bold=True, color="FFFFFF", size=11, name="Calibri")
    hdr_fill = PatternFill("solid", fgColor="003366")
    lbl_font = Font(bold=True, size=10, name="Calibri")
    thin = Border(left=Side("thin", "C0C0C0"), right=Side("thin", "C0C0C0"),
                  top=Side("thin", "C0C0C0"), bottom=Side("thin", "C0C0C0"))

    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 38
    ws.column_dimensions["C"].width = 22

    def hdr(row, cols):
        for i, c in enumerate(cols):
            cell = ws.cell(row, 2 + i, c)
            cell.font = hdr_font; cell.fill = hdr_fill; cell.alignment = Alignment(horizontal="center"); cell.border = thin

    r = 1
    ws.cell(r, 2, "YUSRA PHARMA PLC — INPUT TEMPLATE").font = Font(bold=True, size=14, color="003366")

    r = 3
    ws.cell(r, 2, "PARAMETERS").font = Font(bold=True, size=12, color="003366")
    r = 4
    hdr(r, ["Parameter", "Value", "Notes"])
    params = [
        ("Opening Cash (ETB)", 16927876.79, "Current cash balance"),
        ("Opening Inventory (ETB)", 42000000, "Stock on hand"),
        ("Total Facility (ETB)", 70000000, "Murabaha revolving loan"),
        ("Overheads per Month (ETB)", 1444225.35, "Fixed operating costs"),
        ("Profit Rate (annual)", 0.07, "Murabaha flat rate"),
        ("Loan Tenor (quarters)", 8, "Repayment period"),
    ]
    for i, (lbl, val, note) in enumerate(params):
        rr = r + 1 + i
        ws.cell(rr, 2, lbl).font = lbl_font; ws.cell(rr, 2).border = thin
        ws.cell(rr, 3, val).font = lbl_font; ws.cell(rr, 3).border = thin
        ws.cell(rr, 4, note).font = Font(size=9, italic=True, color="888888")

    r += len(params) + 2
    ws.cell(r, 2, "EXCHANGE RATES").font = Font(bold=True, size=12, color="003366")
    r += 1
    hdr(r, ["Scenario", "Rate", "Active?", "Notes"])
    r += 1
    ws.cell(r, 2, "Baseline").font = lbl_font; ws.cell(r, 3, 160); ws.cell(r, 4, "Yes"); ws.cell(r, 5, "Current rate")
    r += 1
    ws.cell(r, 2, "Stress").font = lbl_font; ws.cell(r, 3, 175); ws.cell(r, 4, ""); ws.cell(r, 5, "Depreciation scenario")

    r += 2
    ws.cell(r, 2, "SALES ASSUMPTIONS").font = Font(bold=True, size=12, color="003366")
    r += 1
    hdr(r, ["Parameter", "Value", "Notes"])
    sales_items = [
        ("Sales Cycle", "3 Months", "3 Months or 6 Months"),
        ("Cash Sales %", 0.85, "Immediate collection"),
        ("Credit Sales %", 0.15, "30-day lag"),
        ("Gross Profit Margin", 0.30, "Markup on COGS"),
    ]
    for i, (lbl, val, note) in enumerate(sales_items):
        rr = r + 1 + i
        ws.cell(rr, 2, lbl).font = lbl_font; ws.cell(rr, 2).border = thin
        ws.cell(rr, 3, val).font = lbl_font; ws.cell(rr, 3).border = thin
        ws.cell(rr, 4, note).font = Font(size=9, italic=True, color="888888")

    r += len(sales_items) + 2
    ws.cell(r, 2, "LOAN PIPELINE").font = Font(bold=True, size=12, color="003366")
    r += 1
    hdr(r, ["Supplier", "USD Value", "ETB Principal", "Start Date", "Quarterly Repayment"])
    sample_loans = [
        ("Reyoung (CHINA)", 147354, 23580195.28, "2026-04-07", 3360178),
        ("SCOTT EDIL (INDIA)", 194100, "", "2026-10-01", ""),
        ("TSM (MALAYSIA)", 42840, "", "2026-10-10", ""),
        ("Tinachin HENGSHENG", 61904, "", "2026-10-10", ""),
    ]
    for i, (sup, usd, etb, sdt, qpmt) in enumerate(sample_loans):
        rr = r + 1 + i
        ws.cell(rr, 2, sup).font = lbl_font; ws.cell(rr, 2).border = thin
        ws.cell(rr, 3, usd).border = thin
        ws.cell(rr, 4, etb).border = thin
        ws.cell(rr, 5, sdt).border = thin
        ws.cell(rr, 6, qpmt).border = thin

    r += len(sample_loans) + 2
    ws.cell(r, 2, "TARGETS").font = Font(bold=True, size=12, color="003366")
    r += 1
    hdr(r, ["Target", "Value (ETB)", "Notes"])
    targets = [
        ("CEO Throughput Goal", 240000000, "3.4x facility utilisation"),
        ("Plan Throughput", 140000000, "2.0x facility utilisation"),
    ]
    for i, (lbl, val, note) in enumerate(targets):
        rr = r + 1 + i
        ws.cell(rr, 2, lbl).font = lbl_font; ws.cell(rr, 2).border = thin
        ws.cell(rr, 3, val).font = lbl_font; ws.cell(rr, 3).border = thin
        ws.cell(rr, 4, note).font = Font(size=9, italic=True, color="888888")

    wb.save(path)
    print(f"Template saved: {path}")
