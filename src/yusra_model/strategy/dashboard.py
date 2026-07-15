"""KPI comparison dashboard — side-by-side scenario and sensitivity tables."""
from __future__ import annotations
from typing import Optional
from .scenario import ScenarioResult

KPI_LABELS: dict[str, str] = {
    "revenue_cagr": "Revenue CAGR",
    "roe": "ROE",
    "avg_roa": "ROA",
    "avg_net_margin": "Net Margin",
    "min_dscr": "Min DSCR",
    "min_cash": "Min Cash",
    "total_throughput": "Total Throughput",
    "final_debt_to_equity": "D/E Ratio",
    "last_year_net_income": "Year-5 Net Income",
}

KPI_FORMATS: dict[str, str] = {
    "revenue_cagr": ".1%",
    "roe": ".1%",
    "avg_roa": ".1%",
    "avg_net_margin": ".1%",
    "min_dscr": ".2f",
    "min_cash": ",.0f",
    "total_throughput": ",.0f",
    "final_debt_to_equity": ".2f",
    "last_year_net_income": ",.0f",
}


def build_comparison(
    results: list[ScenarioResult],
    kpi_keys: Optional[list[str]] = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """Build a comparison table: rows=KPIs, cols=scenarios.

    Returns (headers, rows) where each row is {scenario: formatted_value}.
    """
    if not results:
        return [], []

    if kpi_keys is None:
        kpi_keys = list(KPI_LABELS)

    headers = ["KPI"] + [r.label for r in results]
    rows: list[dict[str, str]] = []

    for key in kpi_keys:
        label = KPI_LABELS.get(key, key)
        fmt = KPI_FORMATS.get(key, ",.2f")
        row: dict[str, str] = {"KPI": label}
        for r in results:
            val = r.kpis.get(key)
            if val is None:
                row[r.label] = "—"
            else:
                try:
                    row[r.label] = format(val, fmt)
                except (ValueError, TypeError):
                    row[r.label] = str(round(val, 2))
        rows.append(row)

    return headers, rows


def print_comparison(results: list[ScenarioResult]) -> None:
    """Print a formatted comparison table to stdout."""
    if not results:
        print("  No scenario results to display.")
        return

    col_w = max(len(r.label) for r in results) + 2
    headers, rows = build_comparison(results)

    sep = "  " + "─" * (18 + col_w * len(results))

    print(sep)
    print(f"  {'KPI':<18}" + "".join(f"{h:>{col_w}}" for h in headers[1:]))
    print(sep)

    for row in rows:
        vals = "".join(f"{v:>{col_w}}" for k, v in row.items() if k != "KPI")
        print(f"  {row['KPI']:<18}{vals}")

    print(sep)
