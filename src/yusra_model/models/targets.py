"""Recycling targets — computed from constraints, not aspirational CEO desires.

The model now computes optimal throughput from actual financial constraints
and compares it honestly against any aspirational targets.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .optimizer import optimize, OptimisationResult, OptimalSolution, ConstraintBoundedMaximum


@dataclass
class RecyclingTarget:
    label: str
    amount_etb: float
    multiplier: float
    description: str
    source: str = "aspirational"  # "aspirational" | "optimal" | "breakeven" | "scenario"


@dataclass
class VelocityScenario:
    scenario: str
    avg_tenor: str
    turns: str
    throughput: str
    throughput_val: float
    feasibility: str
    source: str = "aspirational"


def build_targets(cfg) -> list[RecyclingTarget]:
    """
    Build recycling targets — now driven by the optimisation engine.
    Shows both aspirational (CEO) and computed optimal targets.
    """
    opt = optimize(cfg)
    facility = cfg.total_facility

    targets = [
        RecyclingTarget(
            "Breakeven (Minimum Viable)",
            round(opt.breakeven_throughput, 0),
            round(opt.breakeven_throughput / facility, 1) if facility else 0,
            "Covers overheads + loan profit charges",
            source="optimal",
        ),
        RecyclingTarget(
            "Optimal (Constraint-Bounded)",
            round(opt.optimum.max_throughput, 0),
            opt.optimum.max_multiplier,
            f"{opt.optimum.optimal_tenor}-quarter tenors, bound by {opt.optimum.binding_constraint}",
            source="optimal",
        ),
        RecyclingTarget(
            "Passive (No Recycling)",
            round(facility, 0),
            1.0,
            "Single pass, 8-quarter tenors, no redraws",
            source="scenario",
        ),
    ]

    # Add aspirational target only if it differs from optimal
    if abs(cfg.ceo_throughput_target - opt.optimum.max_throughput) > 0.01 * facility:
        targets.append(
            RecyclingTarget(
                "Aspirational (CEO Goal)",
                cfg.ceo_throughput_target,
                round(cfg.ceo_throughput_target / facility, 1) if facility else 0,
                f"{cfg.ceo_throughput_target / facility:.1f}x facility — requires overcoming '{opt.optimum.binding_constraint}' constraint",
                source="aspirational",
            )
        )

    return sorted(targets, key=lambda t: t.amount_etb)


def build_velocity_scenarios(cfg) -> list[VelocityScenario]:
    """
    Build velocity scenarios from the optimisation sweep results,
    not from hardcoded aspirational targets.
    """
    opt = optimize(cfg)
    facility = cfg.total_facility

    scenarios = []
    for sol in sorted(opt.solutions, key=lambda s: s.tenor_quarters):
        feasible_label = "Feasible" if sol.feasible else f"Constrained by {sol.binding_constraint}"
        scenarios.append(VelocityScenario(
            scenario=f"{sol.tenor_quarters}-Quarter Tenor",
            avg_tenor=f"{sol.tenor_quarters} quarters",
            turns=f"{sol.multiplier:.1f}x",
            throughput=f"ETB {sol.throughput:,.0f}",
            throughput_val=sol.throughput,
            feasibility=feasible_label,
            source="computed",
        ))

    # Add aspirational as reference
    asp_mult = opt.aspirational_target / facility if facility else 0
    constraints_needed = opt.optimum.binding_constraint
    scenarios.append(VelocityScenario(
        scenario="Aspirational (CEO Goal)",
        avg_tenor=f"{opt.optimum.optimal_tenor} qtrs (optimal)",
        turns=f"{opt.aspirational_multiplier:.1f}x",
        throughput=f"ETB {opt.aspirational_target:,.0f}",
        throughput_val=opt.aspirational_target,
        feasibility=f"Requires removing '{constraints_needed}' constraint — not achievable under current parameters",
        source="aspirational",
    ))

    return scenarios


def compute_path_to_240m(base_throughput: float, facility: float) -> list[dict]:
    """Three-step compounding path — now shows optimal stepping stones, not just CEO goal."""
    opt_throughput = _max_theoretical(facility)

    steps = [
        {"step": "1. Initial deployment", "amount": f"{facility/1e6:.0f}M",
         "description": f"Full facility drawn ({facility:,.0f})",
         "cumulative": int(facility)},
    ]

    if opt_throughput > facility:
        steps.append({
            "step": "2. Optimal recycling",
            "amount": f"{(opt_throughput - facility)/1e6:.0f}M",
            "description": f"Redraw repaid principal through optimal {_optimal_tenor(facility)}-quarter cycles",
            "cumulative": int(opt_throughput),
        })

    if base_throughput > opt_throughput:
        steps.append({
            "step": "3. Aspirational stretch",
            "amount": f"{(base_throughput - opt_throughput)/1e6:.0f}M",
            "description": "Requires relaxing constraint (more equity, longer horizon, or higher margin)",
            "cumulative": int(base_throughput),
        })

    return steps


def _max_theoretical(facility: float) -> float:
    """Maximum theoretical throughput with 2-quarter tenors."""
    n = 8  # quarters
    tenor = 2
    cycles = n // tenor  # 4
    return facility * cycles


def _optimal_tenor(facility: float) -> int:
    """Estimate optimal tenor — simplified."""
    return 4  # default to 4-quarter as mid-point
