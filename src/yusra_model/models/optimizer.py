"""Constraint-based optimisation engine — computes optimal throughput, not aspirational targets.

Solves: given financial constraints, what is the maximum achievable throughput?
Then compares optimal vs aspirational (CEO) targets to show the gap honestly.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .loans import _add_quarters
from ..config.loader import Config


MIN_TENOR_QUARTERS = 2       # minimum realistic LC tenor
MAX_TENOR_QUARTERS = 8       # maximum (current)
NUM_CYCLES = 8               # quarters modelled (Q2 2026 - Q4 2028)
MAX_SWEEP_CYCLES = 5         # max full loan cycles in 8 quarters


@dataclass
class OptimalSolution:
    tenor_quarters: int          # optimal LC tenor
    cycles: int                  # number of full cycles achievable
    throughput: float            # total cumulative drawdowns
    multiplier: float            # throughput / facility
    avg_outstanding_pct: float   # avg facility utilisation
    min_closing_cash: float      # lowest closing cash across projection
    dscr: float                  # DSCR at this tenor
    binding_constraint: str      # what limits further optimisation
    feasible: bool               # whether this solution is viable


@dataclass
class ConstraintBoundedMaximum:
    """The true data-driven maximum throughput and the bottleneck."""
    max_throughput: float
    max_multiplier: float
    optimal_tenor: int
    binding_constraint: str
    feasible: bool
    dscr_ok: bool = True
    dscr_at_limit: float = 2.0
    min_cash: float = 0.0
    max_principal: float = 0.0
    facility: float = 0.0


@dataclass
class OptimisationResult:
    facility: float
    profit_rate: float
    overheads_per_quarter: float
    gross_profit_margin: float
    opening_cash: float
    opening_inventory: float
    min_sales_buffer: float
    aspirational_target: float          # what the CEO wants
    aspirational_multiplier: float      # CEO target / facility
    optimum: ConstraintBoundedMaximum    # what is actually achievable
    solutions: list[OptimalSolution]    = field(default_factory=list)
    breakeven_throughput: float         = 0.0
    breakeven_multiplier: float         = 0.0
    gap_to_aspirational: float          = 0.0
    gap_to_optimal: float               = 0.0


def _simulate_tenor(
    tenor: int,
    facility: float,
    profit_rate: float,
    opening_cash: float,
    opening_inventory: float,
    overheads_per_quarter: float,
    gross_profit_margin: float,
    min_cash_buffer: float,
    sales_cycle_3m: bool = True,
) -> OptimalSolution:
    """
    Simulate a full 8-quarter projection with quarterly granularity.

    Each redraw cycle of T quarters:
      - Q0: draw facility → inventory, sell existing stock, repay Q1, pay overheads
      - Q1..T-1: sell remaining stock, repay Qn, pay overheads (no new draw)
    At quarter T the loan is fully repaid; a new cycle may begin.
    """
    n_quarters = NUM_CYCLES
    principal_per_q = facility / tenor
    profit_per_q = facility * profit_rate / 4
    sales_fraction = 1.0 if sales_cycle_3m else 0.5

    cash = opening_cash
    inv = opening_inventory
    cumulative_throughput = 0.0
    min_cash = opening_cash
    worst_dscr = float("inf")
    q_in_cycle = 0
    outstanding = 0.0

    for q in range(n_quarters):
        # Start a new loan cycle if previous is fully repaid
        if q_in_cycle == 0 and outstanding <= 0:
            dd = facility
            cumulative_throughput += dd
            outstanding = dd
            cash += dd
            inv += dd

        # Sell inventory (turn inventory into revenue)
        avail = inv
        cogs = avail * sales_fraction
        rev = cogs * (1 + gross_profit_margin)
        inv = avail - cogs

        # Repay this quarter's installment
        rp = 0.0
        if outstanding > 0:
            principal_paid = min(principal_per_q, outstanding)
            rp = principal_paid + profit_per_q
            outstanding -= principal_paid

        cash += rev - rp - overheads_per_quarter
        min_cash = min(min_cash, cash)

        # DSCR this quarter
        op_cf = rev - overheads_per_quarter
        if rp > 0 and op_cf > 0 and principal_paid > 0:
            dscr_this_q = op_cf / rp
            worst_dscr = min(worst_dscr, dscr_this_q)

        q_in_cycle += 1
        if q_in_cycle >= tenor or outstanding <= 0:
            q_in_cycle = 0

    total_throughput = cumulative_throughput
    multiplier = total_throughput / facility if facility else 0

    binding = "none"
    if worst_dscr != float("inf") and worst_dscr < 1.2:
        binding = "dscr"
    elif min_cash < min_cash_buffer:
        binding = "liquidity"
    elif total_throughput / facility > 5:
        binding = "facility_ceiling"

    feasible = min_cash >= min_cash_buffer and (worst_dscr == float("inf") or worst_dscr >= 1.2)

    return OptimalSolution(
        tenor_quarters=tenor,
        cycles=n_quarters // max(tenor, 1),
        throughput=round(total_throughput, 0),
        multiplier=round(multiplier, 2),
        avg_outstanding_pct=1.0,
        min_closing_cash=round(min_cash, 0),
        dscr=round(worst_dscr, 2) if worst_dscr != float("inf") else 0,
        binding_constraint=binding,
        feasible=feasible,
    )


def _max_throughput_simple(facility: float, profit_rate: float, tenor: int) -> float:
    """
    Simple theoretical maximum throughput for a given LC tenor.

    With N quarters and tenor T: you can cycle the principal floor(N/T) times.
    First cycle: full facility = F
    Subsequent cycles: only principal portion = F * (1 - r*T/4) roughly
    (you must repay profit from operating cash flow, not from redraws)
    """
    n = NUM_CYCLES
    if tenor >= n:
        return facility

    # First cycle draws full facility
    throughput = facility
    remaining_quarters = n - tenor
    # Each subsequent cycle of length T draws (F - profit_on_F)
    # But actually the profit is paid from operations, not from the facility
    # Redraw principal only
    principal_freed_per_cycle = facility / tenor  # per quarter principal repayment
    # Over `tenor` quarters, total principal freed = facility (full principal repaid)
    # So each subsequent cycle can redraw the full facility again
    # But limited by remaining quarters
    while remaining_quarters >= tenor:
        throughput += facility
        remaining_quarters -= tenor

    return throughput


def _find_optimal_tenor(
    facility: float,
    profit_rate: float,
    opening_cash: float,
    opening_inventory: float,
    overheads_per_quarter: float,
    gross_profit_margin: float,
    min_cash_buffer: float,
) -> ConstraintBoundedMaximum:
    """Sweep tenors and find the one that maximises feasible throughput."""
    best_throughput = 0
    best_tenor = MAX_TENOR_QUARTERS
    best_constraint = "none"
    best_sol = None

    for tenor in range(MIN_TENOR_QUARTERS, MAX_TENOR_QUARTERS + 1):
        sol = _simulate_tenor(
            tenor, facility, profit_rate,
            opening_cash, opening_inventory, overheads_per_quarter,
            gross_profit_margin, min_cash_buffer,
        )
        if sol.feasible and sol.throughput > best_throughput:
            best_throughput = sol.throughput
            best_tenor = tenor
            best_constraint = sol.binding_constraint
            best_sol = sol

    # If no tenor is feasible, find the one closest to feasible
    if best_throughput == 0:
        best_throughput = _max_throughput_simple(facility, profit_rate, MAX_TENOR_QUARTERS)
        best_tenor = MAX_TENOR_QUARTERS
        best_constraint = "liquidity_dscr"
        best_sol = _simulate_tenor(MAX_TENOR_QUARTERS, facility, profit_rate,
                                   opening_cash, opening_inventory, overheads_per_quarter,
                                   gross_profit_margin, min_cash_buffer)

    multiplier = best_throughput / facility if facility else 0
    max_p = facility * (NUM_CYCLES // best_tenor) if best_tenor else facility
    return ConstraintBoundedMaximum(
        max_throughput=round(best_throughput, 0),
        max_multiplier=round(multiplier, 2),
        optimal_tenor=best_tenor,
        binding_constraint=best_constraint or "none",
        feasible=best_throughput > 0,
        dscr_ok=(best_sol.dscr >= 1.2) if best_sol else True,
        dscr_at_limit=best_sol.dscr if best_sol else 2.0,
        min_cash=best_sol.min_closing_cash if best_sol else 0,
        max_principal=float(max_p),
        facility=facility,
    )


def _compute_breakeven(
    facility: float,
    profit_rate: float,
    overheads_per_quarter: float,
    gross_profit_margin: float,
    opening_inventory: float,
) -> float:
    """
    Minimum throughput needed to cover:
    - Overheads
    - Loan profit charges (not principal — that's recycled)
    - Maintain operations
    """
    annual_overheads = overheads_per_quarter * 4
    annual_profit = facility * profit_rate
    # Gross profit margin determines how much sales we need
    # to generate enough gross profit to cover overheads + profit
    required_gross_profit = annual_overheads + annual_profit
    if gross_profit_margin <= 0:
        return 0
    required_sales = required_gross_profit / gross_profit_margin
    required_throughput = required_sales + facility  # need at least the facility
    return round(required_throughput, 0)


def optimize(cfg: Config) -> OptimisationResult:
    """Run full optimisation: find the data-driven maximum."""
    facility = cfg.total_facility
    profit_rate = cfg.profit_rate
    overhead_q = cfg.overheads_per_month * 3
    margin = cfg.gross_profit_margin
    min_buffer = cfg.overheads_per_month * 3  # 3 months overheads

    # Aspirational target
    aspirational = cfg.ceo_throughput_target
    aspirational_mult = aspirational / facility if facility else 0

    # Sweep tenors
    solutions = []
    for tenor in range(MIN_TENOR_QUARTERS, MAX_TENOR_QUARTERS + 1):
        sol = _simulate_tenor(
            tenor, facility, profit_rate,
            cfg.opening_cash, cfg.opening_inventory, overhead_q,
            margin, min_buffer,
        )
        solutions.append(sol)

    # Optimal
    optimum = _find_optimal_tenor(
        facility, profit_rate,
        cfg.opening_cash, cfg.opening_inventory, overhead_q, margin, min_buffer,
    )

    # Breakeven
    breakeven = _compute_breakeven(facility, profit_rate, overhead_q, margin, cfg.opening_inventory)
    breakeven_mult = breakeven / facility if facility else 0

    # Gaps
    gap_aspirational = max(0, aspirational - optimum.max_throughput)
    gap_optimal = max(0, optimum.max_throughput - breakeven)

    return OptimisationResult(
        facility=facility,
        profit_rate=profit_rate,
        overheads_per_quarter=overhead_q,
        gross_profit_margin=margin,
        opening_cash=cfg.opening_cash,
        opening_inventory=cfg.opening_inventory,
        min_sales_buffer=min_buffer,
        aspirational_target=aspirational,
        aspirational_multiplier=round(aspirational_mult, 1),
        optimum=optimum,
        solutions=solutions,
        breakeven_throughput=breakeven,
        breakeven_multiplier=round(breakeven_mult, 2),
        gap_to_aspirational=round(gap_aspirational, 0),
        gap_to_optimal=round(gap_optimal, 0),
    )
