# Yusra Model — Transformation Plan

## Goal

Transform from a loan-recycling throughput calculator into a **comprehensive business planning and analysis platform** covering revenue, costs, capital structure, working capital, fixed assets, taxation, and strategic optimization — with the Murabaha facility as one component of the full picture.

## Architecture Principle

> The loan does not drive the business. The business drives the loan.

Current model: `Loan → Inventory → Sales → Recycling → Throughput (goal)`

Target model: `Strategy → Revenue → Operations → Capital → Financing → Optimization`

## Delivery Phases

```
Phase 0 ── Config & Domain Objects (1 week)
            ↓
Phase 1 ── Three-Statement Financial Engine (3 weeks)
            ↓
Phase 2 ── Multi-Dimensional Optimizer (2 weeks)
            ↓
Phase 3 ── Strategy & Planning Module (2 weeks)
            ↓
Phase 4 ── Output Upgrade: Excel, PDF, Dashboard (2 weeks)
```

---

## Phase 0: Config & Domain Objects

### Objective

Expand the data model to capture the full business — revenue drivers, cost structure, capital structure, working capital policy, taxation, and strategic targets — without changing any computation logic. All new fields are optional with sensible defaults; existing configs load unchanged.

### Deliverables

| # | Artifact | Description |
|---|----------|-------------|
| 0a | `src/yusra_model/domain/` package | Dataclasses for all new business domains |
| 0b | `config/schema.json` (expanded) | JSON Schema with new sections (all optional) |
| 0c | `config/default.yaml` (expanded) | Full annotated sample config |
| 0d | `config/loader.py` (extended) | `Config` dataclass grows to hold domain objects; `load_config()` parses them |
| 0e | Backward compatibility tests | All existing 67 tests pass unchanged |

### Detailed Spec

#### 0a — Domain Package Structure

```
src/yusra_model/domain/
├── __init__.py
├── strategy.py      StrategicContext, BusinessTargets
├── revenue.py       RevenueDrivers, ProductLine, SeasonalityProfile, CustomerSegment
├── costs.py         CostStructure, COGSBreakdown, OperatingExpenses, HeadcountPlan
├── capital.py       CapitalStructure, EquityPosition, DebtFacility, FixedAssets,
│                    CapExPlan, WorkingCapitalPolicy, InventoryPolicy,
│                    ReceivablesPolicy, PayablesPolicy
└── taxation.py      TaxSettings
```

Each module contains pure `@dataclass` objects with default factory values. No computation logic.

#### 0b — New Config Sections (all optional in schema)

```yaml
# === STRATEGIC CONTEXT (optional) ===
strategy:
  planning_horizon_years: 5
  base_year: 2025
  targets:
    revenue_growth_annual: 0.15
    gross_margin: 0.28
    operating_margin: 0.12
    net_margin: 0.08
    roe: 0.25
    roic: 0.20
    dscr: 1.5
    debt_to_equity: 1.5
    dividend_payout_ratio: 0.30
    cash_conversion_cycle_days: 60

# === REVENUE DRIVERS (optional) ===
revenue:
  product_lines:
    - name: "Generic Pharmaceuticals"
      base_volume: 250000
      avg_price: 850
      growth_rate: 0.12
      cogs_per_unit: 600
      gross_margin: 0.29
  seasonality: {q1: 0.22, q2: 0.25, q3: 0.24, q4: 0.29}
  cash_ratio: 0.85         # overlaps existing sales.cash_ratio
  credit_ratio: 0.15       # overlaps existing sales.credit_ratio
  credit_terms_days: 30
  bad_debt_rate: 0.005

# === COST STRUCTURE (optional) ===
costs:
  cogs_breakdown:
    raw_materials_pct: 0.55
    import_duties_pct: 0.15
    freight_pct: 0.10
    direct_labor_pct: 0.10
    other_direct_pct: 0.10
  operating_expenses:
    sales_marketing:  {fixed_per_month: 300000, variable_pct_of_revenue: 0.02}
    distribution:     {fixed_per_month: 200000, variable_pct_of_revenue: 0.03}
    admin:            {fixed_per_month: 500000, variable_pct_of_revenue: 0}
    r_and_d:          {fixed_per_month: 100000, variable_pct_of_revenue: 0}
  headcount:
    total_headcount: 45
    avg_cost_per_employee_per_month: 32000
    hiring_growth_rate: 0.05
    salary_escalation_rate: 0.07
  escalation_rate: 0.08

# === CAPITAL STRUCTURE (optional) ===
capital:
  equity:
    paid_in_capital: 15000000
    retained_earnings: 25000000
  debt:
    - facility: 70000000
      type: "Murabaha_Revolving"
      profit_rate: 0.07
      tenor_quarters: 8
      purpose: "Inventory financing"
  target_debt_to_equity: 1.5

# === FIXED ASSETS (optional) ===
fixed_assets:
  existing_assets:
    - cost: 35000000
      accumulated_depreciation: 12000000
      useful_life_years: 10
      depreciation_method: "straight_line"
  capex_plan:
    year_1: 5000000
    year_2: 3000000
    year_3: 2000000
    year_4: 2000000
    year_5: 1000000

# === WORKING CAPITAL POLICY (optional) ===
working_capital:
  inventory:
    raw_materials_days: 45
    wip_days: 15
    finished_goods_days: 60
    safety_stock_days: 15
    obsolescence_rate: 0.02
  receivables:
    dso_target: 30
    bad_debt_rate: 0.005
  payables:
    dpo_target: 45
  cash_conversion_cycle_target: 60

# === TAXATION (optional) ===
taxation:
  corporate_income_tax_rate: 0.30
  vat_rate: 0.15
  withholding_tax_rate: 0.05
  tax_loss_carryforward_years: 5
```

#### 0c — Backward Compatibility Rules

| Rule | Implementation |
|------|---------------|
| Configs without new sections load normally | All new Config fields default to `None` or empty domain objects with defaults |
| Existing parameter names unchanged | `parameters.opening_cash` still at root; new domains are separate sections |
| The `sales` block is now legacy input | New `revenue` block supersedes it when present; `sales` used as fallback |
| The `targets` block extended | Add new target fields alongside existing `ceo_throughput`, `plan_throughput` |

#### 0d — Config Dataclass Changes

```python
@dataclass
class Config:
    # Existing fields (unchanged)
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

    # New domain fields (all optional with defaults)
    strategy: StrategicContext | None = None
    revenue: RevenueDrivers | None = None
    costs: CostStructure | None = None
    capital_structure: CapitalStructure | None = None
    fixed_assets: FixedAssets | None = None
    working_capital_policy: WorkingCapitalPolicy | None = None
    taxation: TaxSettings | None = None
```

#### 0e — Test Plan

- Existing 67 tests pass unchanged (new fields are all optional)
- New tests:
  - Domain dataclass default construction
  - Schema accepts config without new sections
  - Schema accepts config with all new sections
  - Config loader populates domain objects when sections present
  - Config loader returns None for missing sections
  - Revenue → product_lines parsing
  - Capital → debt facilities parsing
  - Fixed assets → asset list + CapEx parsing
  - Working capital policy default values
  - Tax settings default values

---

## Phase 1: Three-Statement Engine (Preview)

*Detailed plan to follow after Phase 0 delivery.*

- Monthly-granularity projection engine
- Driver-based P&L (revenue build-up → COGS → gross profit → OpEx → EBITDA → D&A → EBIT → interest → tax → net income)
- Balance Sheet (A = L + E, period-over-period roll-forward)
- Cash Flow Statement (operating, investing, financing)
- Balancing checks on every period
- Loan model runs as a sub-module inside the debt schedule
- Covenant tracking on projected statements (multi-period, forward-looking)

---

## Phase 2: Multi-Dimensional Optimizer (Preview)

- Optimization across revenue growth vs margin, working capital efficiency, capital structure, risk constraints
- The loan throughput optimizer becomes one dimension of the full optimizer
- Output: optimal revenue target, margin target, DSO/DPO/DIO targets, leverage target

---

## Phase 3: Strategy & Planning Module (Preview)

- Multi-horizon planning (strategic 5yr → annual → quarterly)
- Strategic initiatives with resource allocation
- OKR/KPI tree
- Scenario engine with auto-sweep
- Variance tracking (plan vs actual, rolling forecast)

---

## Phase 4: Output Upgrade (Preview)

- Extended Excel: P&L sheet, Balance Sheet sheet, Cash Flow sheet
- Enhanced PDF with full financial statements
- Optional: interactive HTML dashboard (Plotly Dash) for what-if exploration

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Data availability — real business data may not exist for new fields | High | Medium | All new fields optional; use defaults; Phase 0 surfaces gaps early |
| Scope creep — adding computation in Phase 0 | Medium | High | Phase 0 is strictly data structures only; no engine changes |
| Breaking existing users | Low | High | All new schema fields optional; existing tests must pass unchanged |
| Domain object complexity — too many nested dataclasses | Medium | Low | Flat structure where possible; sensible defaults everywhere |
| Performance with 5-year monthly data | Low | Low | Numpy/pandas if needed; lazy evaluation |

---

## How to Read This Plan

Each phase is a self-contained delivery that adds value independently. Phase 0 does not change any computation — it only expands what the model knows about the business. Phase 1 is where the new data starts producing financial statements. Phases 2–4 build the planning and optimization layers on top.

The plan assumes the Python scripting approach (YAML config + CLI + Excel/PDF output) is retained. If the business later outgrows this, the domain objects and engine can be extracted into a web service without rewriting the core logic.
