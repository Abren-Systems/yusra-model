"""CLI entry point for yusra-model"""
from __future__ import annotations
import sys
from pathlib import Path
import click
from yusra_model.config.loader import load_config, generate_input_template
from yusra_model.output.excel import build_workbook


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
def run(config, output, fmt, name):
    """Run the financial model and generate outputs."""
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Loading config from {config}...")
    cfg = load_config(config)

    click.echo(f"Building portfolio ({len(cfg.loans)} loans)...")
    from yusra_model.models.loans import Loan, Portfolio
    loans = [Loan(**l) for l in cfg.loans]
    portfolio = Portfolio(loans, cfg.total_facility, cfg.profit_rate)
    portfolio.allocate_remaining()

    click.echo("Running cash flow projection...")
    from yusra_model.models.cashflow import project
    overhead_q = cfg.overheads_per_month * 3
    proj = project(portfolio, cfg.opening_cash, cfg.opening_inventory, overhead_q, cfg.gross_profit_margin)

    if fmt in ("xlsx", "xlsx+pdf"):
        xlsx_path = output_dir / f"{name}.xlsx"
        click.echo(f"Generating Excel workbook: {xlsx_path}...")
        result = build_workbook(cfg, xlsx_path)
        click.echo(f"  [OK] Excel saved: {result}")

    if fmt in ("pdf", "xlsx+pdf"):
        pdf_path = output_dir / f"{name}.pdf"
        click.echo(f"Generating PDF report: {pdf_path}...")
        try:
            from yusra_model.output.pdf import build_pdf
            result = build_pdf(cfg, portfolio, proj, pdf_path)
            click.echo(f"  [OK] PDF saved: {result}")
        except Exception as e:
            click.echo(f"  [FAIL] PDF generation failed: {e}", err=True)
            click.echo("  (WeasyPrint may require system dependencies. Try: --format xlsx)")

    click.echo("Done.")


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
