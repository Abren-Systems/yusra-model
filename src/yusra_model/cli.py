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
def run(config, output, fmt, name, verbose, scenario):
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

    # Select cycle based on scenario
    cycle_map = {"base": "3 Months", "upside": "3 Months", "downside": "6 Months", "stress": "6 Months"}
    active_cycle = cycle_map.get(scenario, "3 Months")
    active_proj = proj.select_cycle(active_cycle)
    logger.info("Active sales cycle: %s (%s rows)", active_cycle, len(active_proj.rows))

    # Build audit metadata
    audit = {
        "run_id": run_id,
        "timestamp": timestamp,
        "scenario": scenario,
        "active_cycle": active_cycle,
        "config_file": str(config),
        "model_version": "1.1.0",
    }

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
            logger.error("PDF generation failed: %s", e, exc_info=verbose)
            click.echo(f"  [FAIL] PDF generation failed: {e}", err=True)
            click.echo("  (WeasyPrint may require system dependencies. Try: --format xlsx)")

    # Write audit log
    log_path = output_dir / f"run_{run_id}.json"
    import json
    with open(log_path, "w") as f:
        json.dump(audit, f, indent=2)
    logger.info("Audit log written: %s", log_path)

    logger.info("Run %s complete.", run_id)
    click.echo(f"Run {run_id} complete. Output in: {output_dir}")


@cli.command()
@click.option("--config", "-c", default="config/default.yaml",
              help="Path to YAML config file (default: config/default.yaml)")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def optimize_cmd(config, verbose):
    """Run the throughput optimiser and show constraint-bounded maximum."""
    _setup_logging(verbose)
    from yusra_model.models.optimizer import optimize
    cfg = load_config(config)
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


@cli.command()
@click.option("--output", "-o", default="./config/template.xlsx",
              help="Output path for the Excel input template")
def init(output):
    """Generate a blank Excel input template."""
    generate_input_template(output)
    click.echo(f"Template generated: {output}")
    click.echo("Fill in the template with your data, then run:")
    click.echo(f"  yusra-model run --config {output} --output ./reports/")


if __name__ == "__main__":
    cli()
