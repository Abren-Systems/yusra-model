"""PDF report builder — WeasyPrint + Plotly charts"""
from __future__ import annotations
from pathlib import Path
import tempfile
from jinja2 import Environment, PackageLoader
import plotly.graph_objects as go
import plotly.io as pio
from yusra_model.config.loader import Config
from yusra_model.models.loans import Portfolio
from yusra_model.models.cashflow import CashFlowProjection, QUARTER_LABELS
from yusra_model.models.targets import build_targets, build_velocity_scenarios


def _render_chart(fig: go.Figure, width: int = 700, height: int = 400) -> str:
    """Render a plotly figure to a base64 PNG for embedding in HTML."""
    import base64
    img_bytes = pio.to_image(fig, format="png", width=width, height=height, scale=2)
    return base64.b64encode(img_bytes).decode("utf-8")


def _cash_chart(proj: CashFlowProjection) -> str:
    qlabels = [r.quarter for r in proj.rows]
    cash = [r.closing_cash for r in proj.rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=qlabels, y=cash, mode="lines+markers",
                             name="Closing Cash", line=dict(color="#4472C4", width=3),
                             marker=dict(size=8, color="#4472C4")))
    fig.update_layout(title="Cash Balance Trend (ETB)", xaxis_title="Quarter",
                      yaxis_title="ETB", template="plotly_white",
                      hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40))
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    return _render_chart(fig)


def _util_chart(proj: CashFlowProjection) -> str:
    qlabels = [r.quarter for r in proj.rows]
    util = [r.facility_util_pct * 100 for r in proj.rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=qlabels, y=util, name="Facility Util %",
                         marker=dict(color="#BF8F00")))
    fig.update_layout(title="Facility Utilization %", xaxis_title="Quarter",
                      yaxis_title="%", template="plotly_white",
                      hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40))
    fig.add_hline(y=80, line_dash="dash", line_color="red",
                  annotation_text="80% Target")
    return _render_chart(fig)


def _repayment_chart(portfolio: Portfolio, proj: CashFlowProjection) -> str:
    qlabels = [r.quarter for r in proj.rows]
    repayments = [r.repayments for r in proj.rows]
    draws = [r.drawdowns for r in proj.rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=qlabels, y=draws, name="Drawdowns",
                         marker=dict(color="#548235")))
    fig.add_trace(go.Bar(x=qlabels, y=repayments, name="Repayments",
                         marker=dict(color="#4472C4")))
    fig.update_layout(title="Drawdowns vs Repayments", xaxis_title="Quarter",
                      yaxis_title="ETB", barmode="group", template="plotly_white",
                      hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40))
    return _render_chart(fig)


def _scenario_chart(proj: CashFlowProjection) -> str:
    qlabels = [r.quarter for r in proj.rows[:8]]
    sales_3m = [r.sales_inflow_3m for r in proj.rows[:8]]
    sales_6m = [r.sales_inflow_6m for r in proj.rows[:8]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=qlabels, y=sales_3m, name="3-Month Cycle",
                         marker=dict(color="#548235")))
    fig.add_trace(go.Bar(x=qlabels, y=sales_6m, name="6-Month Cycle",
                         marker=dict(color="#BF8F00")))
    fig.update_layout(title="Sales Inflow: 3-Month vs 6-Month Cycle",
                      xaxis_title="Quarter", yaxis_title="ETB",
                      barmode="group", template="plotly_white",
                      hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40))
    return _render_chart(fig)


def _throughput_chart(proj: CashFlowProjection) -> str:
    qlabels = [r.quarter for r in proj.rows]
    draws = [r.drawdowns for r in proj.rows]
    cumulative = []
    total = 0
    for d in draws:
        total += d
        cumulative.append(total)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=qlabels, y=cumulative, mode="lines+markers",
                             name="Cumulative Throughput",
                             line=dict(color="#002060", width=3),
                             marker=dict(size=8, color="#002060")))
    fig.add_hline(y=240000000, line_dash="dash", line_color="red",
                  annotation_text="240M CEO Goal")
    fig.add_hline(y=140000000, line_dash="dot", line_color="green",
                  annotation_text="140M Plan Target")
    fig.update_layout(title="Recycling Throughput (Cumulative Drawdowns)",
                      xaxis_title="Quarter", yaxis_title="ETB",
                      template="plotly_white", hovermode="x unified",
                      margin=dict(l=40, r=20, t=40, b=40))
    return _render_chart(fig)


def build_pdf(cfg: Config, portfolio: Portfolio, proj: CashFlowProjection,
              output_path: str | Path) -> str:
    """Generate PDF report using WeasyPrint."""
    from weasyprint import HTML

    targets = build_targets(cfg.ceo_throughput_target, cfg.total_facility)
    scenarios = build_velocity_scenarios()

    context = {
        "company": cfg.company,
        "currency": cfg.currency,
        "total_facility": f"{cfg.total_facility:,.0f}",
        "opening_cash": f"{cfg.opening_cash:,.2f}",
        "opening_inventory": f"{cfg.opening_inventory:,.0f}",
        "overheads_monthly": f"{cfg.overheads_per_month:,.2f}",
        "profit_rate": f"{cfg.profit_rate*100:.0f}%",
        "total_principal": f"{portfolio.total_principal:,.0f}",
        "total_quarterly_repayment": f"{portfolio.total_quarterly_repayment:,.0f}",
        "total_profit": f"{portfolio.total_profit:,.2f}",
        "ceo_target": f"{cfg.ceo_throughput_target:,.0f}",
        "ceo_multiplier": f"{cfg.ceo_throughput_target/cfg.total_facility:.1f}x",
        "num_loans": len(portfolio.loans),
        "loan_table": [
            {"supplier": l.supplier, "usd": f"{l.usd_value:,.0f}",
             "etb": f"{l.etb_principal:,.0f}", "start": l.start_date.isoformat(),
             "quarterly": f"{l.quarterly_repayment:,.0f}"}
            for l in portfolio.loans
        ],
        "quarterly_table": [
            {"quarter": r.quarter, "opening_cash": f"{r.opening_cash:,.0f}",
             "drawdowns": f"{r.drawdowns:,.0f}", "repayments": f"{r.repayments:,.0f}",
             "sales_3m": f"{r.sales_inflow_3m:,.0f}", "sales_6m": f"{r.sales_inflow_6m:,.0f}",
             "overheads": f"{r.overheads:,.0f}", "net_cf": f"{r.net_cash_flow:,.0f}",
             "closing_cash": f"{r.closing_cash:,.0f}", "util_pct": f"{r.facility_util_pct*100:.1f}%"}
            for r in proj.rows
        ],
        "targets": [
            {"label": t.label, "amount": f"ETB {t.amount_etb:,.0f}" if t.amount_etb < 1e9 else f"ETB {t.amount_etb/1e6:.0f}M",
             "multiplier": f"{t.multiplier:.1f}x", "description": t.description}
            for t in targets
        ],
        "scenarios": [
            {"scenario": s.scenario, "avg_tenor": s.avg_tenor, "turns": s.turns,
             "throughput": s.throughput, "feasibility": s.feasibility}
            for s in scenarios
        ],
        "chart_cash": _cash_chart(proj),
        "chart_util": _util_chart(proj),
        "chart_repayment": _repayment_chart(portfolio, proj),
        "chart_scenario": _scenario_chart(proj),
        "chart_throughput": _throughput_chart(proj),
    }

    env = Environment()
    template_str = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
@page { size: A4; margin: 1.5cm; font-family: 'Calibri', sans-serif; font-size: 10pt; color: #333; }
h1 { color: #002060; font-size: 18pt; margin-bottom: 4px; }
h2 { color: #002060; font-size: 14pt; border-bottom: 2px solid #002060; padding-bottom: 4px; margin-top: 20px; }
h3 { color: #4472C4; font-size: 12pt; margin-top: 14px; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 9pt; }
th { background: #002060; color: white; padding: 5px 4px; text-align: center; }
td { padding: 4px; border: 1px solid #ccc; text-align: center; }
td.left { text-align: left; }
.kpi-row { display: flex; justify-content: space-between; gap: 8px; margin: 10px 0; }
.kpi-card { flex: 1; background: #E8EAF6; border: 2px solid #002060; border-radius: 4px; padding: 8px; text-align: center; }
.kpi-card .label { font-size: 8pt; color: #555; }
.kpi-card .value { font-size: 14pt; font-weight: bold; color: #002060; }
.kpi-card .value.ceo { font-size: 14pt; font-weight: bold; color: #C00000; background: #FCE4EC; }
.ceo-row th { background: #C00000; }
.ceo-row td { background: #FCE4EC; font-weight: bold; }
.chart { margin: 12px 0; text-align: center; }
.chart img { max-width: 100%; height: auto; }
.page-break { page-break-before: always; }
.note { font-size: 8pt; color: #888; font-style: italic; }
</style></head>
<body>
<h1>{{ company }}</h1>
<p style="font-size:10pt;color:#666;margin-top:-4px;">Murabaha Revolving Loan Facility — Financial Model Report</p>

<div class="kpi-row">
<div class="kpi-card"><div class="label">Total Facility</div><div class="value">ETB {{ total_facility }}</div></div>
<div class="kpi-card"><div class="label">Total Principal Drawn</div><div class="value">ETB {{ total_principal }}</div></div>
<div class="kpi-card"><div class="label">Quarterly Repayment</div><div class="value">ETB {{ total_quarterly_repayment }}</div></div>
<div class="kpi-card"><div class="label">CEO Throughput Target</div><div class="value ceo">ETB {{ ceo_target }}</div></div>
</div>

<h2>1. Executive Summary</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td class="left">Opening Cash Balance</td><td>ETB {{ opening_cash }}</td></tr>
<tr><td class="left">Opening Inventory</td><td>ETB {{ opening_inventory }}</td></tr>
<tr><td class="left">Monthly Overheads</td><td>ETB {{ overheads_monthly }}</td></tr>
<tr><td class="left">Profit Rate (Murabaha)</td><td>{{ profit_rate }}</td></tr>
<tr><td class="left">Total Profit Charges (8 qtrs)</td><td>ETB {{ total_profit }}</td></tr>
<tr><td class="left">CEO Throughput Target</td><td>ETB {{ ceo_target }} ({{ ceo_multiplier }})</td></tr>
</table>

<div class="chart"><h3>Cash Balance Trend</h3><img src="data:image/png;base64,{{ chart_cash }}" /></div>
<div class="chart"><h3>Recycling Throughput</h3><img src="data:image/png;base64,{{ chart_throughput }}" /></div>

<div class="page-break"></div>

<h2>2. Loan Portfolio</h2>
<table>
<tr><th>Supplier</th><th>USD Value</th><th>ETB Principal</th><th>Start Date</th><th>Quarterly Repayment</th></tr>
{% for l in loan_table %}
<tr><td class="left">{{ l.supplier }}</td><td>{{ l.usd }}</td><td>{{ l.etb }}</td><td>{{ l.start }}</td><td>{{ l.quarterly }}</td></tr>
{% endfor %}
</table>

<div class="chart"><h3>Drawdowns vs Repayments</h3><img src="data:image/png;base64,{{ chart_repayment }}" /></div>
<div class="chart"><h3>Facility Utilization</h3><img src="data:image/png;base64,{{ chart_util }}" /></div>

<div class="page-break"></div>

<h2>3. Quarterly Projection</h2>
<table>
<tr><th>Quarter</th><th>Opening Cash</th><th>Drawdowns</th><th>Repayments</th><th>Sales (3m)</th><th>Sales (6m)</th><th>Overheads</th><th>Net CF</th><th>Closing Cash</th><th>Util %</th></tr>
{% for r in quarterly_table %}
<tr><td>{{ r.quarter }}</td><td>{{ r.opening_cash }}</td><td>{{ r.drawdowns }}</td><td>{{ r.repayments }}</td><td>{{ r.sales_3m }}</td><td>{{ r.sales_6m }}</td><td>{{ r.overheads }}</td><td>{{ r.net_cf }}</td><td>{{ r.closing_cash }}</td><td>{{ r.util_pct }}</td></tr>
{% endfor %}
</table>

<div class="chart"><h3>Sales Inflow: 3-Month vs 6-Month Cycle</h3><img src="data:image/png;base64,{{ chart_scenario }}" /></div>

<div class="page-break"></div>

<h2>4. CEO Stretch Goal: ETB {{ ceo_target }}</h2>
<h3>Velocity Scenarios</h3>
<table>
<tr><th>Scenario</th><th>Avg LC Tenor</th><th>Turns in 8 Qtrs</th><th>Throughput</th><th>Feasibility</th></tr>
{% for s in scenarios %}
<tr{% if 'CEO' in s.scenario %} class="ceo-row"{% endif %}>
<td class="left">{{ s.scenario }}</td><td>{{ s.avg_tenor }}</td><td>{{ s.turns }}</td><td>{{ s.throughput }}</td><td>{{ s.feasibility }}</td>
</tr>
{% endfor %}
</table>

<h3>Recycling Targets</h3>
<table>
<tr><th>Target</th><th>Amount</th><th>Multiplier</th><th>Description</th></tr>
{% for t in targets %}
<tr{% if 'CEO' in t.label %} class="ceo-row"{% endif %}>
<td class="left">{{ t.label }}</td><td>{{ t.amount }}</td><td>{{ t.multiplier }}</td><td class="left">{{ t.description }}</td>
</tr>
{% endfor %}
</table>

<p class="note">Generated by yusra-model v1.0.0 | {{ company }}</p>
</body></html>"""

    template = env.from_string(template_str)
    html_content = template.render(**context)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_content).write_pdf(str(output_path))

    return str(output_path)
