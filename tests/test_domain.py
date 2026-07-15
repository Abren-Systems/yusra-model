"""Tests for business domain data objects."""
from __future__ import annotations
from yusra_model.domain import (
    StrategicContext, BusinessTargets,
    RevenueDrivers, ProductLine, SeasonalityProfile, CustomerSegment,
    CostStructure, COGSBreakdown, OperatingExpenses, OpExCategory, HeadcountPlan,
    EquityPosition, DebtFacility, DepreciableAsset, CapExPlan, FixedAssets,
    InventoryPolicy, ReceivablesPolicy, PayablesPolicy, WorkingCapitalPolicy,
    TaxSettings,
)


class TestDomainDefaults:
    """Every domain dataclass must construct with no arguments."""

    def test_business_targets_defaults(self):
        t = BusinessTargets()
        assert t.roe == 0.25
        assert t.dscr == 1.5

    def test_strategic_context_defaults(self):
        s = StrategicContext()
        assert s.planning_horizon_years == 5
        assert s.targets.dscr == 1.5

    def test_product_line_requires_name(self):
        p = ProductLine(name="Test")
        assert p.base_volume == 0.0

    def test_seasonality_normalises(self):
        s = SeasonalityProfile(q1=0.5, q2=0.5, q3=0, q4=0)
        assert abs(s.q1 + s.q2 + s.q3 + s.q4 - 1.0) < 0.001

    def test_revenue_drivers_defaults(self):
        r = RevenueDrivers()
        assert r.cash_ratio == 0.85
        assert len(r.product_lines) == 0

    def test_cogs_breakdown_normalises(self):
        c = COGSBreakdown(raw_materials_pct=1, import_duties_pct=1,
                          freight_pct=0, direct_labor_pct=0, other_direct_pct=0)
        assert abs(c.raw_materials_pct + c.import_duties_pct + c.freight_pct
                   + c.direct_labor_pct + c.other_direct_pct - 1.0) < 0.001

    def test_opex_category_defaults(self):
        o = OpExCategory()
        assert o.fixed_per_month == 0.0
        assert o.variable_pct_of_revenue == 0.0

    def test_headcount_defaults(self):
        h = HeadcountPlan()
        assert h.total_headcount == 0

    def test_cost_structure_defaults(self):
        c = CostStructure()
        assert c.escalation_rate == 0.08

    def test_equity_position(self):
        e = EquityPosition(paid_in_capital=10_000_000, retained_earnings=5_000_000)
        assert e.total_equity == 15_000_000

    def test_debt_facility_defaults(self):
        d = DebtFacility()
        assert d.type == "Murabaha_Revolving"
        assert d.profit_rate == 0.07

    def test_depreciable_asset_defaults(self):
        a = DepreciableAsset()
        assert a.depreciation_method == "straight_line"

    def test_capex_plan_year_access(self):
        p = CapExPlan(year_1=100, year_2=200, year_3=300, year_4=400, year_5=500)
        assert p.for_year(0) == 100
        assert p.for_year(4) == 500
        assert p.for_year(5) == 0.0

    def test_fixed_assets_defaults(self):
        f = FixedAssets()
        assert len(f.existing_assets) == 0
        assert f.capex_plan.year_1 == 0.0

    def test_inventory_policy_defaults(self):
        i = InventoryPolicy()
        assert i.raw_materials_days == 45

    def test_receivables_policy_defaults(self):
        r = ReceivablesPolicy()
        assert r.dso_target == 30

    def test_payables_policy_defaults(self):
        p = PayablesPolicy()
        assert p.dpo_target == 45

    def test_working_capital_policy_defaults(self):
        w = WorkingCapitalPolicy()
        assert w.cash_conversion_cycle_target == 60

    def test_tax_settings_defaults(self):
        t = TaxSettings()
        assert t.corporate_income_tax_rate == 0.30
        assert t.vat_rate == 0.15
