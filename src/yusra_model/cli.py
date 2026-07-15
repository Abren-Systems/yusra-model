"""CLI entry point for yusra-model"""
from __future__ import annotations
import sys
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
import click
from yusra_model.config.loader import load_config, generate_input_template
from yusra_model.config.validation import validate_business_rules
from yusra_model.output.excel import build_workbook

logger = logging.getLogger("yusra_model")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.group()
@click.version_option(package_name="yusra-model", prog_name="yusra-model")
def cli():
    """YUSRA PHARMA PLC — Murabaha Revolving Loan Financial Model"""


@cli.command()
@click.option("--config", "-c", default="config/default.yaml",
              help="Path to YAML config file (default: config/default.yaml)")
@click.option("--output", "-o", default="./reports/",
              help="Output directory (default: ./reports/)")
@click.option("--format", "-f", "fmt", default="xlsx+pdf",
              type=click.Choice(["xlsx", "pdf", "xlsx+pdf"]),
              help="Output format (default: xlsx+pdf)")
@click.option("--name", "-n", default="YUSRA_PHARMA_Financial_Model",
              help="Output file name prefix")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--scenario", "-s", default="base",
              type=click.Choice(["base", "upside", "downside", "stress"]),
              help="Scenario preset (default: base)")
@click.option("--full", "-F", is_flag=True, default=False,
              help="Run full three-statement projection instead of legacy loan model")
def run(config, output, fmt, name, verbose, scenario, full):
    """Run the financial model and generate outputs."""
    _setup_logging(verbose)
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now(timezone.utc).isoformat()

    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Run %s | Scenario: %s | Config: %s", run_id, scenario, config)
    cfg = load_config(config)

    # Business-rule warnings
    warnings = validate_business_rules(cfg)
    for w in warnings:
        logger.warning("Config: %s", w)
        click.echo(f"  [WARN] {w}")

    audit = {
        "run_id": run_id,
        "timestamp": timestamp,
        "scenario": scenario,
        "config_file": str(config),
        "model_version": "1.2.0",
    }

    if full:
        _run_full(cfg, fmt, output_dir, name, run_id, audit)
    else:
        _run_legacy(cfg, fmt, scenario, output_dir, name, run_id, audit)

    # Write audit log
    log_path = output_dir / f"run_{run_id}.json"
    import json
    with open(log_path, "w") as f:
        json.dump(audit, f, indent=2)
    logger.info("Audit log written: %s", log_path)
    logger.info("Run %s complete.", run_id)
    click.echo(f"Run {run_id} complete. Output in: {output_dir}")


def _run_full(cfg, fmt, output_dir, name, run_id, audit):
    """Run the full three-statement projection engine."""
    logger.info("Running full three-statement projection...")
    from yusra_model.engine import project_full
    full_proj = project_full(cfg)
    audit["active_cycle"] = "annual"
    click.echo(f"  Projection: {full_proj.n_quarters} quarters, all balanced={full_proj.all_balanced()}")
    if fmt in ("xlsx", "xlsx+pdf"):
        xlsx_path = output_dir / f"{name}_{run_id}.xlsx"
        logger.info("Generating Excel workbook: %s", xlsx_path)
        from yusra_model.output.full_excel import build_full_workbook
        result = build_full_workbook(cfg, full_proj, audit, xlsx_path)
        click.echo(f"  [OK] {result}")
    if fmt in ("pdf", "xlsx+pdf"):
        click.echo(f"  [SKIP] Full PDF output not yet implemented. Use --format xlsx")


def _run_legacy(cfg, fmt, scenario, output_dir, name, run_id, audit):
    """Run the legacy loan-recycling model."""
    logger.info("Building portfolio (%d loans)...", len(cfg.loans))
    from yusra_model.models.loans import Loan, Portfolio
    loans = [Loan(**l) for l in cfg.loans]
    portfolio = Portfolio(tuple(loans), cfg.total_facility, cfg.profit_rate)
    portfolio = portfolio.with_allocated_remaining()
    logger.debug("Portfolio: total_principal=%.2f, remaining=%.2f",
                 portfolio.total_principal, portfolio.remaining_facility())

    logger.info("Running cash flow projection...")
    from yusra_model.models.cashflow import project
    overhead_q = cfg.overheads_per_month * 3
    proj = project(portfolio, cfg.opening_cash, cfg.opening_inventory, overhead_q, cfg.gross_profit_margin)

    cycle_map = {"base": "3 Months", "upside": "3 Months", "downside": "6 Months", "stress": "6 Months"}
    active_cycle = cycle_map.get(scenario, "3 Months")
    active_proj = proj.select_cycle(active_cycle)
    audit["active_cycle"] = active_cycle
    logger.info("Active sales cycle: %s (%s rows)", active_cycle, len(active_proj.rows))

    if fmt in ("xlsx", "xlsx+pdf"):
        xlsx_path = output_dir / f"{name}_{run_id}.xlsx"
        logger.info("Generating Excel workbook: %s", xlsx_path)
        result = build_workbook(cfg, portfolio, proj, active_proj, audit, xlsx_path)
        click.echo(f"  [OK] {result}")

    if fmt in ("pdf", "xlsx+pdf"):
        pdf_path = output_dir / f"{name}_{run_id}.pdf"
        logger.info("Generating PDF report: %s", pdf_path)
        try:
            from yusra_model.output.pdf import build_pdf
            result = build_pdf(cfg, portfolio, proj, active_proj, pdf_path, audit)
            click.echo(f"  [OK] {result}")
        except Exception as e:
            logger.error("PDF generation failed: %s", e, exc_info=True)
            click.echo(f"  [FAIL] PDF generation failed: {e}", err=True)
            click.echo("  (WeasyPrint may require system dependencies. Try: --format xlsx)")


@cli.command()
@click.option("--config", "-c", default="config/default.yaml",
              help="Path to YAML config file (default: config/default.yaml)")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--full", "-F", is_flag=True, default=False,
              help="Run multi-dimensional optimizer (full business sweep) instead of legacy throughput")
@click.option("--top", "-n", default=10, type=int,
              help="Number of top configurations to show (default: 10)")
def optimize_cmd(config, verbose, full, top):
    """Run the business optimizer and show optimal configurations.

    Without --full: runs the legacy loan-throughput optimizer (tenor sweep).
    With --full: runs the multi-dimensional optimizer (growth, margin, WC, leverage, tenor).
    """
    _setup_logging(verbose)
    cfg = load_config(config)

    if full:
        _run_multi_optimizer(cfg, top)
    else:
        _run_legacy_optimizer(cfg)


def _run_legacy_optimizer(cfg):
    """Legacy throughput optimizer — single-dimension tenor sweep."""
    from yusra_model.models.optimizer import optimize
    result = optimize(cfg)
    click.echo(f"\n{'='*60}")
    click.echo(f"THROUGHPUT OPTIMISATION — {cfg.company}")
    click.echo(f"{'='*60}")
    click.echo(f"  Facility:            ETB {result.facility:,.0f}")
    click.echo(f"  Aspirational target: ETB {result.aspirational_target:,.0f}")
    click.echo(f"  Breakeven:           ETB {result.breakeven_throughput:,.0f} ({result.breakeven_multiplier:.1f}x)")
    click.echo(f"  ───────────────────────────────────────────")
    o = result.optimum
    click.echo(f"  OPTIMAL THROUGHPUT:  ETB {o.max_throughput:,.0f} ({o.max_multiplier:.1f}x)")
    click.echo(f"  Optimal tenor:       {o.optimal_tenor} quarters")
    click.echo(f"  Binding constraint:  {o.binding_constraint}")
    click.echo(f"  DSCR at limit:       {o.dscr_at_limit:.2f} (target ≥1.2)")
    click.echo(f"  Min closing cash:    ETB {o.min_cash:,.0f}")
    click.echo(f"  Gap to aspirational: ETB {result.gap_to_aspirational:,.0f}")
    click.echo(f"{'='*60}")
    click.echo(f"\nSweep results ({len(result.solutions)} tenors):")
    for sol in sorted(result.solutions, key=lambda s: s.tenor_quarters):
        flag = "✓" if sol.feasible else "✗"
        click.echo(
            f"  {flag} {sol.tenor_quarters}-qtr: "
            f"ETB {sol.throughput:,.0f} ({sol.multiplier:.1f}x) "
            f"| min_cash=ETB {sol.min_closing_cash:,.0f} "
            f"| dscr={sol.dscr:.2f}"
            f"{'  → ' + sol.binding_constraint if not sol.feasible else ''}"
        )


def _run_multi_optimizer(cfg, top_n):
    """Multi-dimensional business optimizer — full grid sweep."""
    from yusra_model.models.multi_optimizer import run_optimizer, DEFAULT_GRID

    click.echo(f"\n{'='*60}")
    click.echo(f"MULTI-DIMENSIONAL OPTIMISATION — {cfg.company}")
    click.echo(f"{'='*60}")

    grid = DEFAULT_GRID
    total = 1
    for v in grid.values():
        total *= len(v)

    click.echo(f"  Grid dimensions:")
    for k, v in grid.items():
        click.echo(f"    {k}: {v}")
    click.echo(f"  Total variants: {total}")

    with click.progressbar(length=total, label="  Running projections...") as bar:
        def progress(i, t):
            bar.update(1)
        result = run_optimizer(cfg, progress_callback=progress)

    click.echo(f"  Feasible: {result.n_feasible} / {len(result.variants)}")

    if result.n_feasible == 0:
        click.echo("  No feasible configurations found (all violate constraints).")
        click.echo("  Try relaxing constraints or adjusting the baseline config.")
        return

    top = result.ranked(n=top_n)
    click.echo(f"\n  ─── TOP {len(top)} CONFIGURATIONS (weighted score) ───")
    click.echo(f"  {'Rank':<5} {'Growth':<8} {'Price':<8} {'WC Eff':<8} {'Leverage':<10} {'Tenor':<6} "
               f"{'ROE':<8} {'CAGR':<8} {'DSCR':<8} {'Thr\'put':<12} {'Score':<8}")
    click.echo(f"  {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*10} {'─'*6} "
               f"{'─'*8} {'─'*8} {'─'*8} {'─'*12} {'─'*8}")

    for i, v in enumerate(top):
        p = v.params
        k = v.kpis
        click.echo(
            f"  {i+1:<5} {p.get('growth_multiplier', 1.0):<8} {p.get('price_multiplier', 1.0):<8} "
            f"{p.get('wc_efficiency', 1.0):<8} "
            f"{p.get('leverage_multiplier', 1.0):<10} "
            f"{p.get('tenor_quarters', '—'):<6} "
            f"{k.get('roe', 0):>7.1%} {k.get('revenue_cagr', 0):>7.1%} "
            f"{k.get('min_dscr', 0):>7.2f} "
            f"{k.get('total_throughput', 0):>11,.0f}"
        )

    # Pareto frontiers
    click.echo(f"\n  ─── PARETO FRONTIERS ───")
    for obj_a, obj_b, label in [
        ("roe", "revenue_cagr", "ROE vs Revenue Growth"),
        ("roe", "min_dscr", "ROE vs DSCR (risk)"),
    ]:
        front = result.pareto_front(obj_a, obj_b)
        click.echo(f"\n  {label} ({len(front)} points on frontier):")
        for v in front[:5]:
            p = v.params
            k = v.kpis
            click.echo(
                f"    ROE={k.get('roe', 0):>6.1%}  CAGR={k.get('revenue_cagr', 0):>6.1%}  "
                f"DSCR={k.get('min_dscr', 0):>5.2f}  "
                f"growth={p.get('growth_multiplier', 1.0)} price={p.get('price_multiplier', 1.0)}"
            )
        if len(front) > 5:
            click.echo(f"    ... ({len(front) - 5} more)")

    click.echo(f"\n{'='*60}")


@cli.command()
@click.option("--output", "-o", default="./config/template.xlsx",
              help="Output path for the Excel input template")
def init(output):
    """Generate a blank Excel input template."""
    generate_input_template(output)
    click.echo(f"Template generated: {output}")
    click.echo("Fill in the template with your data, then run:")
    click.echo(f"  yusra-model run --config {output} --output ./reports/")


@cli.command()
@click.option("--config", "-c", default="config/default.yaml",
              help="Path to YAML config file (default: config/default.yaml)")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.option("--scenarios", "-s", default="base,upside,downside,stress",
              help="Comma-separated scenario list (default: base,upside,downside,stress)")
@click.option("--sensitivity", is_flag=True, default=False,
              help="Run sensitivity analysis in addition to scenarios")
def plan(config, verbose, scenarios, sensitivity):
    """Run scenario analysis and strategic planning."""
    _setup_logging(verbose)
    cfg = load_config(config)

    scenario_names = [s.strip() for s in scenarios.split(",") if s.strip()]

    click.echo(f"\n{'='*60}")
    click.echo(f"STRATEGIC PLANNING ANALYSIS — {cfg.company}")
    click.echo(f"{'='*60}")
    click.echo(f"  Scenarios: {', '.join(scenario_names)}")

    from yusra_model.strategy.scenario import run_scenarios
    from yusra_model.strategy.dashboard import print_comparison

    results = run_scenarios(cfg, scenario_names)

    click.echo(f"\n  ─── SCENARIO COMPARISON ───")
    print_comparison(results)

    if sensitivity:
        click.echo(f"\n  ─── SENSITIVITY ANALYSIS ───")
        from yusra_model.strategy.sensitivity import run_sensitivity

        sens = run_sensitivity(cfg)
        click.echo(f"\n  Base KPIs: ROE={sens.base_kpis.get('roe', 0):.1%}  "
                   f"DSCR={sens.base_kpis.get('min_dscr', 0):.2f}  "
                   f"Yr-5 NI={sens.base_kpis.get('last_year_net_income', 0):,.0f}")
        click.echo()

        for driver in ["growth", "price", "wc", "leverage", "cost_escalation"]:
            points = sens.for_driver(driver)
            if not points:
                continue
            click.echo(f"  Driver: {driver}")
            click.echo(f"  {'Change':>8} {'ROE Δ':>10} {'DSCR Δ':>10} {'Yr-5 NI Δ':>14}")
            click.echo(f"  {'─'*8} {'─'*10} {'─'*10} {'─'*14}")
            for p in points:
                click.echo(
                    f"  {p.change_pct:>+7d}%  "
                    f"{p.delta_kpis.get('roe', 0):>+9.1%}  "
                    f"{p.delta_kpis.get('min_dscr', 0):>+9.2f}  "
                    f"{p.delta_kpis.get('last_year_net_income', 0):>+13,.0f}"
                )
            click.echo()

    click.echo(f"{'='*60}")


if __name__ == "__main__":
    cli()
