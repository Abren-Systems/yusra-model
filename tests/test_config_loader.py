"""Tests for config loader — backward compat + new domain sections."""
from __future__ import annotations
import yaml
import json
from pathlib import Path
from jsonschema import validate as json_validate, ValidationError
from yusra_model.config.loader import load_config


SCHEMA_PATH = Path(__file__).parent.parent / "config" / "schema.json"


def _validate(raw: dict) -> None:
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    json_validate(raw, schema)


def _minimal_legacy() -> dict:
    """Minimal config matching the original schema (no new sections)."""
    return {
        "company": "Test Co",
        "currency": "ETB",
        "parameters": {
            "opening_cash": 10_000_000,
            "opening_inventory": 20_000_000,
            "total_facility": 70_000_000,
            "overheads_per_month": 1_000_000,
            "profit_rate": 0.07,
            "loan_tenor_quarters": 8,
        },
        "exchanges": {"baseline": 160, "stress": 175},
        "sales": {
            "cycle_options": ["3 Months", "6 Months"],
            "cash_ratio": 0.85,
            "credit_ratio": 0.15,
            "gross_profit_margin": 0.30,
        },
        "loans": [
            {"supplier": "A", "usd_value": 100_000, "start_date": "2026-04-07",
             "etb_principal": 16_000_000, "effective_rate": 160.0, "quarterly_repayment": 2_500_000},
        ],
        "targets": {
            "ceo_throughput": 240_000_000,
            "plan_throughput": 140_000_000,
            "min_sales_buffer": 500_000,
        },
    }


class TestSchemaBackwardCompat:
    """New schema must accept all old configs without new sections."""

    def test_minimal_legacy_validates(self):
        _validate(_minimal_legacy())

    def test_minimal_legacy_loads(self, tmp_path):
        yml = tmp_path / "config.yaml"
        with open(yml, "w") as f:
            yaml.dump(_minimal_legacy(), f)
        cfg = load_config(yml)
        assert cfg.company == "Test Co"
        assert cfg.strategy is None
        assert cfg.revenue is None
        assert cfg.costs is None
        assert cfg.capital == []
        assert cfg.equity is None
        assert cfg.fixed_assets is None
        assert cfg.working_capital_policy is None
        assert cfg.taxation is None

    def test_full_config_validates(self):
        raw = _minimal_legacy()
        raw["strategy"] = {
            "planning_horizon_years": 5,
            "base_year": 2025,
            "targets": {"revenue_growth_annual": 0.15, "gross_margin": 0.28},
        }
        raw["revenue"] = {
            "product_lines": [{"name": "Test Product", "base_volume": 1000, "avg_price": 500}],
        }
        raw["costs"] = {
            "operating_expenses": {
                "admin": {"fixed_per_month": 500_000},
            },
            "headcount": {"total_headcount": 50, "avg_cost_per_employee_per_month": 30_000},
        }
        raw["capital"] = {
            "equity": {"paid_in_capital": 15_000_000, "retained_earnings": 25_000_000},
            "debt": [{"facility": 70_000_000, "type": "Murabaha_Revolving", "profit_rate": 0.07}],
        }
        raw["fixed_assets"] = {
            "existing_assets": [{"cost": 35_000_000, "accumulated_depreciation": 12_000_000,
                                 "useful_life_years": 10}],
            "capex_plan": {"year_1": 5_000_000},
        }
        raw["working_capital"] = {
            "inventory": {"raw_materials_days": 45},
            "receivables": {"dso_target": 30},
            "payables": {"dpo_target": 45},
        }
        raw["taxation"] = {"corporate_income_tax_rate": 0.30}
        _validate(raw)

    def test_full_config_loads(self, tmp_path):
        raw = _minimal_legacy()
        raw["strategy"] = {"planning_horizon_years": 5}
        raw["revenue"] = {
            "product_lines": [{"name": "Generics", "base_volume": 250_000, "avg_price": 850}],
            "seasonality": {"q1": 0.22, "q2": 0.25, "q3": 0.24, "q4": 0.29},
        }
        raw["costs"] = {
            "headcount": {"total_headcount": 45, "avg_cost_per_employee_per_month": 32_000},
        }
        raw["capital"] = {
            "equity": {"paid_in_capital": 15_000_000, "retained_earnings": 25_000_000},
            "debt": [{"facility": 70_000_000, "type": "Murabaha_Revolving"}],
        }
        raw["taxation"] = {"corporate_income_tax_rate": 0.30}
        yml = tmp_path / "full_config.yaml"
        with open(yml, "w") as f:
            yaml.dump(raw, f)
        cfg = load_config(yml)
        assert cfg.company == "Test Co"
        assert cfg.strategy is not None
        assert cfg.strategy.planning_horizon_years == 5
        assert cfg.revenue is not None
        assert len(cfg.revenue.product_lines) == 1
        assert cfg.revenue.product_lines[0].name == "Generics"
        assert cfg.costs is not None
        assert cfg.costs.headcount.total_headcount == 45
        assert len(cfg.capital) == 1
        assert cfg.capital[0].facility == 70_000_000
        assert cfg.equity is not None
        assert cfg.equity.paid_in_capital == 15_000_000
        assert cfg.taxation is not None
        assert cfg.taxation.corporate_income_tax_rate == 0.30
        assert cfg.fixed_assets is None  # not provided
        assert cfg.working_capital_policy is None  # not provided

    def test_default_yaml_is_valid(self):
        """The shipped default.yaml must pass schema validation."""
        yml_path = Path(__file__).parent.parent / "config" / "default.yaml"
        with open(yml_path) as f:
            raw = yaml.safe_load(f)
        _validate(raw)
        cfg = load_config(yml_path)
        assert cfg.company == "YUSRA PHARMA PLC"
        assert cfg.strategy is not None
        assert cfg.revenue is not None
        assert len(cfg.revenue.product_lines) == 3
        assert cfg.costs is not None
        assert len(cfg.capital) == 1
        assert cfg.equity is not None
        assert cfg.fixed_assets is not None
        assert cfg.working_capital_policy is not None
        assert cfg.taxation is not None
