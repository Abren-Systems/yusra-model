"""Recycling targets and path calculations"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RecyclingTarget:
    label: str
    amount_etb: float
    multiplier: float
    description: str


@dataclass
class VelocityScenario:
    scenario: str
    avg_tenor: str
    turns: str
    throughput: str
    feasibility: str


def build_targets(ceo_target: float, facility: float) -> list[RecyclingTarget]:
    return [
        RecyclingTarget("Minimum (Passive)", round(facility * 1.5, 0), 1.5, "6-month cycle, basic redraws"),
        RecyclingTarget("Target (Active)", round(facility * 2.0, 0), 2.0, "3-month cycle + active redraw"),
        RecyclingTarget("Stretch (Aggressive)", round(facility * 2.5, 0), 2.5, "Prepayment + shorter tenors"),
        RecyclingTarget("CEO GOAL", ceo_target, round(ceo_target / facility, 1), "All levers: 3-mo sales, 4-qtr LCs, prepay"),
    ]


def build_velocity_scenarios() -> list[VelocityScenario]:
    return [
        VelocityScenario("Passive - no recycling", "8 quarters", "1.0x", "70M", "Current state"),
        VelocityScenario("Standard - redraw only", "8+4 qtrs", "1.7x", "120M", "Redraw, no short tenors"),
        VelocityScenario("Active - 4-qtr tenors", "4 quarters", "2.0x", "140M", "Plan target"),
        VelocityScenario("Aggressive - prepay+short", "~3 quarters", "2.5x", "175M", "Stretch target"),
        VelocityScenario("CEO - maximum velocity", "~2.3 quarters", "3.4x", "240M", "3-mo sales + 6-mo inv + prepay"),
    ]


def compute_path_to_240m(base_throughput: float, facility: float) -> list[dict]:
    """Three-step compounding path to 240M."""
    step1 = round(facility, 0)
    step2 = round(facility * 2, 0)
    step3 = round(facility * 3.43, 0)
    return [
        {"step": "1. Initial 4 LCs", "amount": f"{round(step1/1e6,0):.0f}M", "description": "Reyoung + Scott Edil + TSM + Tinachin (8-quarter tenors)", "cumulative": int(step1)},
        {"step": "2. Redraw repaid principal", "amount": f"{round(step1/1e6,0):.0f}M", "description": "All principal repaid in 8 quarters -> immediately redrawn", "cumulative": int(step2)},
        {"step": "3. Redraw repaid REDRAWN principal", "amount": "100M", "description": "Redrawn LCs use 4-quarter tenors -> repaid + redrawn AGAIN within 2yr", "cumulative": int(step3)},
    ]
