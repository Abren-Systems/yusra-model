# yusra-model

YUSRA PHARMA PLC — Murabaha Revolving Loan Financial Model

A Python CLI tool that generates a comprehensive 5-sheet Excel workbook and PDF report for modelling a Murabaha revolving loan facility, import pipeline, repayments, sales inflows, overheads, inventory turnover, and strategic planning with recycling throughput targets.

## Quick Start

```bash
pip install .
yusra-model run --config config/default.yaml --output ./reports/
```

Or with Docker:

```bash
docker build -t yusra-model .
docker run --rm -v ./reports:/data/reports yusra-model run --config config/default.yaml --output /data/reports/
```

## Usage

```bash
# Run with default config, generate Excel + PDF
yusra-model run

# Specify config and output directory
yusra-model run --config my_portfolio.yaml --output ./my_reports/

# Generate Excel only
yusra-model run --format xlsx

# Generate PDF only
yusra-model run --format pdf

# Generate input template
yusra-model init --output template.xlsx
yusra-model run --config template.xlsx
```

## Output

- **Excel**: 5-sheet workbook (Inputs, Loan_Repayment_Schedule, Quarterly_Projection, Liquidity_Dashboard, Strategic_Plan)
- **PDF**: Board-ready report with Plotly charts (cash trend, facility utilisation, drawdowns vs repayments, scenario comparison, recycling throughput)

## Configuration

Edit `config/default.yaml` to change:
- Opening cash / inventory / facility amount
- Overheads, profit rate, exchange rates
- Sales cycle (3m/6m), margins, cash/credit split
- Loan pipeline (add/remove suppliers)
- Throughput targets (CEO 240M, plan targets)

## Install

```bash
git clone <repo>
cd yusra-model
pip install .
```
