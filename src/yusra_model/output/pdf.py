"""PDF report builder — WeasyPrint + Plotly charts"""
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, PackageLoader
import plotly.graph_objects as go
import plotly.io as pio
from yusra_model.config.loader import Config
from yusra_model.models.loans import Portfolio
from yusra_model.models.cashflow import CashFlowProjection, CycleProjection, QUARTER_LABELS
from yusra_model.models.optimizer import optimize
from yusra_model.models.targets import build_targets, build_velocity_scenarios
from yusra_model.models.covenants import check_all


def _render_chart(fig: go.Figure, width: int = 700, height: int = 400) -> str:
    import base64
    img_bytes = pio.to_image(fig, format="png", width=width, height=height, scale=2)
    return base64.b64encode(img_bytes).decode("utf-8")


def _cash_chart(rows: list) -> str:
    qlabels = [r.quarter for r in rows]
    cash = [r.closing_cash for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=qlabels, y=cash, mode="lines+markers",
                             name="Closing Cash", line=dict(color="#4472C4", width=3),
                             marker=dict(size=8, color="#4472C4")))
    fig.update_layout(title="Cash Balance Trend (ETB)", xaxis_title="Quarter",
                      yaxis_title="ETB", template="plotly_white",
                      hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40))
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    return _render_chart(fig)


def _util_chart(rows: list) -> str:
    qlabels = [r.quarter for r in rows]
    util = [r.facility_util_pct * 100 for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=qlabels, y=util, name="Facility Util %",
                         marker=dict(color="#BF8F00")))
    fig.update_layout(title="Facility Utilization %", xaxis_title="Quarter",
                      yaxis_title="%", template="plotly_white",
                      hovermode="x unified", margin=dict(l=40, r=20, t=40, b=40))
    fig.add_hline(y=80, line_dash="dash", line_color="red",
                  annotation_text="80% Warning")
    fig.add_hline(y=100, line_dash="dot", line_color="darkred",
                  annotation_text="100% Limit")
    return _render_chart(fig)


def _repayment_chart(rows: list) -> str:
    qlabels = [r.quarter for r in rows]
    repayments = [r.repayments for r in rows]
    draws = [r.drawdowns for r in rows]
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
    qlabels = [r.quarter for r in proj.proj_3m.rows[:8]]
    sales_3m = [r.sales_inflow for r in proj.proj_3m.rows[:8]]
    sales_6m = [r.sales_inflow for r in proj.proj_6m.rows[:8]]
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


def _throughput_chart(rows: list) -> str:
    qlabels = [r.quarter for r in rows]
    draws = [r.drawdowns for r in rows]
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


def _murabaha_apr_equivalent(flat_rate: float, tenor_quarters: int) -> float:
    n = tenor_quarters
    flat_factor = 1.0 + flat_rate * (n / 4)
    pmt = flat_factor / n
    lo, hi = 0.0, 0.5
    for _ in range(50):
        mid = (lo + hi) / 2
        if mid > 1e-12:
            f = pmt - (mid * (1 + mid) ** n) / ((1 + mid) ** n - 1)
        else:
            f = pmt - 1.0 / n
        if f > 0:
            lo = mid
        else:
            hi = mid
    qrate = (lo + hi) / 2
    return round(qrate * 4 * 100, 1)


def _covenant_kpi_html(covenants: list) -> str:
    rows_html = ""
    for c in covenants:
        color = {"pass": "green", "warning": "#BF8F00", "breach": "red"}.get(c.status, "gray")
        rows_html += f"<tr><td>{c.metric}</td><td>{c.value_str}</td><td>{c.threshold_str}</td><td style='color:{color};font-weight:bold'>{c.status.upper()}</td></tr>"
    return rows_html


def build_pdf(cfg: Config, portfolio: Portfolio, proj: CashFlowProjection,
              active_proj: CycleProjection, output_path: str | Path,
              audit: dict | None = None) -> str:
    """Generate PDF report using WeasyPrint."""
    from weasyprint import HTML

    opt_result = optimize(cfg)
    targets = build_targets(cfg)
    scenarios = build_velocity_scenarios(cfg)
    covenants = check_all(portfolio, active_proj, cfg)

    apr_eq = _murabaha_apr_equivalent(cfg.profit_rate, cfg.loan_tenor_quarters)
    active_rows = active_proj.rows

    context = {
        "company": cfg.company,
        "currency": cfg.currency,
        "total_facility": f"{cfg.total_facility:,.0f}",
        "opening_cash": f"{cfg.opening_cash:,.2f}",
        "opening_inventory": f"{cfg.opening_inventory:,.0f}",
        "overheads_monthly": f"{cfg.overheads_per_month:,.2f}",
        "profit_rate": f"{cfg.profit_rate*100:.0f}%",
        "profit_rate_apr": f"{apr_eq:.1f}%",
        "total_principal": f"{portfolio.total_principal:,.0f}",
        "total_quarterly_repayment": f"{portfolio.total_quarterly_repayment:,.0f}",
        "total_profit": f"{portfolio.total_profit:,.2f}",
        "aspirational_target": f"{cfg.ceo_throughput_target:,.0f}",
        "aspirational_multiplier": f"{cfg.ceo_throughput_target/cfg.total_facility:.1f}x",
        "optimal_throughput": f"{opt_result.optimum.max_throughput:,.0f}",
        "optimal_multiplier": f"{opt_result.optimum.max_multiplier:.1f}x",
        "optimal_tenor": opt_result.optimum.optimal_tenor,
        "binding_constraint": opt_result.optimum.binding_constraint,
        "breakeven_throughput": f"{opt_result.breakeven_throughput:,.0f}",
        "gap_aspirational": f"{opt_result.gap_to_aspirational:,.0f}",
        "num_loans": len(portfolio.loans),
        "active_cycle": active_proj.cycle_name,
        "run_id": (audit or {}).get("run_id", "?"),
        "scenario": (audit or {}).get("scenario", "base"),
        "loan_table": [
            {"supplier": l.supplier, "usd": f"{l.usd_value:,.0f}",
             "etb": f"{l.etb_principal:,.0f}", "start": l.start_date.isoformat(),
             "quarterly": f"{l.quarterly_repayment:,.0f}"}
            for l in portfolio.loans
        ],
        "quarterly_table": [
            {"quarter": r.quarter, "opening_cash": f"{r.opening_cash:,.0f}",
             "drawdowns": f"{r.drawdowns:,.0f}", "repayments": f"{r.repayments:,.0f}",
             "sales": f"{r.sales_inflow:,.0f}",
             "overheads": f"{r.overheads:,.0f}", "net_cf": f"{r.net_cash_flow:,.0f}",
             "closing_cash": f"{r.closing_cash:,.0f}", "util_pct": f"{r.facility_util_pct*100:.1f}%"}
            for r in active_rows
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
        "covenant_table": _covenant_kpi_html(covenants),
        "chart_cash": _cash_chart(active_rows),
        "chart_util": _util_chart(active_rows),
        "chart_repayment": _repayment_chart(active_rows),
        "chart_scenario": _scenario_chart(proj),
        "chart_throughput": _throughput_chart(active_rows),
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
.tag { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 8pt; font-weight: bold; color: white; }
.tag-pass { background: green; }
.tag-warning { background: #BF8F00; }
.tag-breach { background: red; }
.meta { font-size: 8pt; color: #999; margin-bottom: 10px; }
</style></head>
<body>
<h1>{{ company }}</h1>
<p class="meta">Run {{ run_id }} | Scenario: {{ scenario }} | Active Cycle: {{ active_cycle }}</p>
<p style="font-size:10pt;color:#666;margin-top:-4px;">Murabaha Revolving Loan Facility — Financial Model Report</p>

<div class="kpi-row">
<div class="kpi-card"><div class="label">Total Facility</div><div class="value">ETB {{ total_facility }}</div></div>
<div class="kpi-card"><div class="label">Total Principal Drawn</div><div class="value">ETB {{ total_principal }}</div></div>
<div class="kpi-card"><div class="label">Quarterly Repayment</div><div class="value">ETB {{ total_quarterly_repayment }}</div></div>
<div class="kpi-card"><div class="label">Optimal Throughput</div><div class="value" style="color:#002060;">ETB {{ optimal_throughput }}</div></div>
<div class="kpi-card"><div class="label">Aspirational Target</div><div class="value ceo">ETB {{ aspirational_target }}</div></div>
</div>

<h2>1. Executive Summary</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td class="left">Opening Cash Balance</td><td>ETB {{ opening_cash }}</td></tr>
<tr><td class="left">Opening Inventory</td><td>ETB {{ opening_inventory }}</td></tr>
<tr><td class="left">Monthly Overheads</td><td>ETB {{ overheads_monthly }}</td></tr>
<tr><td class="left">Profit Rate (Murabaha, flat)</td><td>{{ profit_rate }}</td></tr>
<tr><td class="left">APR-Equivalent (declining-balance)</td><td>{{ profit_rate_apr }}</td></tr>
<tr><td class="left">Total Profit Charges (8 qtrs)</td><td>ETB {{ total_profit }}</td></tr>
<tr><td class="left">Optimal Throughput (computed)</td><td>ETB {{ optimal_throughput }} ({{ optimal_multiplier }}) — bound by {{ binding_constraint }}</td></tr>
<tr><td class="left">Aspirational Target (CEO)</td><td>ETB {{ aspirational_target }} ({{ aspirational_multiplier }}) — gap ETB {{ gap_aspirational }}</td></tr>
<tr><td class="left">Breakeven Throughput</td><td>ETB {{ breakeven_throughput }}</td></tr>
<tr><td class="left">Active Sales Cycle</td><td>{{ active_cycle }}</td></tr>
</table>
<p class="note">Murabaha profit is computed on a flat-rate basis ({{ profit_rate }}). The APR-equivalent ({{ profit_rate_apr }}) is shown for like-for-like comparison with declining-balance financing. This difference is structural to Islamic finance, not additional cost.</p>

<h2>Covenant Monitoring</h2>
<table>
<tr><th>Metric</th><th>Value</th><th>Threshold</th><th>Status</th></tr>
{{ covenant_table }}
</table>

<div class="chart"><h3>Cash Balance Trend ({{ active_cycle }})</h3><img src="data:image/png;base64,{{ chart_cash }}" /></div>
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

<h2>3. Quarterly Projection ({{ active_cycle }})</h2>
<table>
<tr><th>Quarter</th><th>Opening Cash</th><th>Drawdowns</th><th>Repayments</th><th>Sales</th><th>Overheads</th><th>Net CF</th><th>Closing Cash</th><th>Util %</th></tr>
{% for r in quarterly_table %}
<tr><td>{{ r.quarter }}</td><td>{{ r.opening_cash }}</td><td>{{ r.drawdowns }}</td><td>{{ r.repayments }}</td><td>{{ r.sales }}</td><td>{{ r.overheads }}</td><td>{{ r.net_cf }}</td><td>{{ r.closing_cash }}</td><td>{{ r.util_pct }}</td></tr>
{% endfor %}
</table>

<div class="chart"><h3>Sales Inflow: 3-Month vs 6-Month Cycle</h3><img src="data:image/png;base64,{{ chart_scenario }}" /></div>

<div class="page-break"></div>

<h2>4. Target Analysis: Optimal vs Aspirational</h2>
<p>Computed maximum feasible throughput: <strong>ETB {{ optimal_throughput }}</strong> ({{ optimal_multiplier }}) at {{ optimal_tenor }}-quarter tenors, constrained by <strong>{{ binding_constraint }}</strong>.</p>

<h3>Velocity Scenarios</h3>
<table>
<tr><th>Scenario</th><th>Avg LC Tenor</th><th>Turns in 8 Qtrs</th><th>Throughput</th><th>Feasibility</th></tr>
{% for s in scenarios %}
<tr{% if 'Aspirational' in s.scenario %} class="ceo-row"{% endif %}>
<td class="left">{{ s.scenario }}</td><td>{{ s.avg_tenor }}</td><td>{{ s.turns }}</td><td>{{ s.throughput }}</td><td>{{ s.feasibility }}</td>
</tr>
{% endfor %}
</table>

<h3>Recycling Targets</h3>
<table>
<tr><th>Target</th><th>Amount</th><th>Multiplier</th><th>Description</th></tr>
{% for t in targets %}
<tr{% if 'Aspirational' in t.label %} class="ceo-row"{% endif %}>
<td class="left">{{ t.label }}</td><td>{{ t.amount_etb }}</td><td>{{ t.multiplier }}</td><td class="left">{{ t.description }}</td>
</tr>
{% endfor %}
</table>

<p class="note">Generated by yusra-model v1.1.0 | Run {{ run_id }} | {{ company }}</p>
</body></html>"""

    template = env.from_string(template_str)
    html_content = template.render(**context)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_content).write_pdf(str(output_path))

    return str(output_path)
