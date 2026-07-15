"""Sheet 5: Strategic Plan & Targets"""
from __future__ import annotations
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ═══ Module-level style constants ═══
FONT_ACCENT  = Font(bold=True, color="FFFFFF", size=10, name="Calibri")
FONT_SECTION = Font(bold=True, size=12, color="002060", name="Calibri")
FONT_BOLD    = Font(bold=True, size=10, name="Calibri")
FONT_14R     = Font(bold=True, size=14, color="C00000", name="Calibri")
FONT_12B     = Font(bold=True, size=12, color="002060", name="Calibri")
FONT_10_ITAL = Font(italic=True, size=10, color="555555", name="Calibri")
FONT_10_GREY = Font(italic=True, size=10, color="888888", name="Calibri")
FONT_BOLD_C  = Font(bold=True, size=10, color="C00000", name="Calibri")
FONT_12B_C   = Font(bold=True, size=12, color="C00000", name="Calibri")
FONT_14B_C   = Font(bold=True, size=14, color="C00000", name="Calibri")
FONT_9       = Font(size=9, name="Calibri")
FONT_9_ITAL  = Font(size=9, italic=True, name="Calibri")

GP   = PatternFill("solid", fgColor="E2EFDA")
YP   = PatternFill("solid", fgColor="FFF2CC")
BP   = PatternFill("solid", fgColor="D6E4F0")
RP   = PatternFill("solid", fgColor="FCE4EC")
GOLP = PatternFill("solid", fgColor="FFF8E1")
HP   = PatternFill("solid", fgColor="002060")

THIN  = Border(left=Side('thin','C0C0C0'), right=Side('thin','C0C0C0'),
               top=Side('thin','C0C0C0'), bottom=Side('thin','C0C0C0'))
AC    = Alignment(horizontal='center', wrap_text=True)
ACT   = Alignment(horizontal='center')
AWT   = Alignment(wrap_text=True)


def build(ws, cfg, portfolio):
    ws.title = "Strategic_Plan"
    ws.sheet_properties.tabColor = "002060"
    ws.sheet_view.showGridLines = False
    for col, w in [(1, 2), (2, 30), (3, 24), (4, 50), (5, 22), (6, 22)]:
        ws.column_dimensions[chr(64 + col)].width = w

    ws.merge_cells('B1:F1')
    c = ws['B1']
    c.value = "STRATEGIC PLAN - TARGETS & OPERATIONAL ROADMAP"
    c.font = Font(bold=True, size=14, color="002060", name="Calibri")

    ws.merge_cells('B2:F2')
    c = ws['B2']
    c.value = f"{cfg.company} | CFO Strategic Framework"
    c.font = Font(italic=True, size=10, color="666666")

    r = 4
    _tr(ws, r, "PRIMARY OBJECTIVE: MAXIMISE LOAN RECYCLING THROUGHPUT", FONT_SECTION)
    r += 1
    _tr(ws, r,
        f"Goal: Every ETB repaid must be immediately re-drawn. Target: {cfg.ceo_throughput_target:,.0f} ETB ({cfg.ceo_throughput_target / cfg.total_facility:.1f}x facility) within 2 years.",
        FONT_10_ITAL)
    r += 2

    # ▓▓▓ CEO 240M GOAL ▓▓▓
    _tr(ws, r, f"CEO STRETCH GOAL: ETB {cfg.ceo_throughput_target:,.0f} THROUGHPUT ({cfg.ceo_throughput_target / cfg.total_facility:.1f}x FACILITY)", FONT_14R, RP, AC)
    r += 1
    _tr(ws, r, f"How to reach {cfg.ceo_throughput_target:,.0f} from current {portfolio.total_principal:,.0f} baseline", FONT_10_GREY)
    r += 1

    # 3-step compounding header
    for i, h in enumerate(['Step', 'Amount', 'How', 'Cumulative']):
        _hdr(ws, r, 2 + i, h)
    r += 1

    for lbl, amt, desc, cum, pf in [
        ('1. Initial 4 LCs', f"{cfg.total_facility / 1e6:.0f}M", 'Reyoung + Scott Edil + TSM + Tinachin (8-quarter tenors)', int(cfg.total_facility), GP),
        ('2. Redraw repaid principal', f"{cfg.total_facility / 1e6:.0f}M", 'All principal repaid in 8 quarters -> immediately redrawn', int(cfg.total_facility * 2), BP),
        (f'3. Redraw repaid REDRAWN principal', f"{cfg.ceo_throughput_target / 1e6 - cfg.total_facility * 2 / 1e6:.0f}M", 'Redrawn LCs use 4-quarter tenors -> repaid + redrawn AGAIN within 2yr', int(cfg.ceo_throughput_target), RP),
    ]:
        _cv(ws, r, 2, lbl, FONT_BOLD, pf, THIN)
        _cv(ws, r, 3, amt, FONT_14B_C, pf, THIN, ACT)
        _cv(ws, r, 4, desc, FONT_9, pf, THIN, AWT)
        _cv(ws, r, 5, '', None, pf, THIN)
        _cv(ws, r, 6, cum, FONT_12B, pf, THIN, ACT, '#,##0')
        r += 1

    r += 1
    _tr(ws, r, "CRITICAL REQUIREMENTS FOR 240M CEO GOAL", FONT_SECTION)
    r += 1
    for req in [
        '[1] All NEW redrawn LCs must have 4-quarter (max) tenors - 8-quarter locks capacity too long',
        '[2] First redraws (Q3/Q4 2026) mature in Q3/Q4 2027 - those ~3M chunks must be redrawn AGAIN',
        '[3] From Q1 2027 ~8.75M frees each quarter -> draw 4-quarter LCs -> mature in 4 qtrs -> redraw again',
        '[4] Prepayment clause: early repayment -> immediate full redraw for new 4-quarter cycle',
        '[5] Avg LC tenor ~2.3 quarters (= 8 qtrs / 3.4 turns). Requires fast inventory turnover.',
        '[6] Sales cycle MUST be 3 months. 6-month cycle makes 240M impossible.',
    ]:
        for cc in range(2, 7):
            cell = ws.cell(r, cc)
            cell.value = req if cc == 2 else ''
            cell.font = FONT_9
            cell.fill = GOLP
            cell.alignment = AWT
        r += 1

    r += 1
    _tr(ws, r, "VELOCITY SCENARIO COMPARISON", FONT_SECTION)
    r += 1
    for i, h in enumerate(['Scenario', 'Avg LC Tenor', 'Turns in 8 Qtrs', 'Throughput', 'Feasibility']):
        _hdr(ws, r, 2 + i, h)
    r += 1

    for sc, ten, turns, thr, feas, pf in [
        ('Passive - no recycling', '8 quarters', '1.0x', '70M', 'Current state', YP),
        ('Standard - redraw only', '8+4 qtrs', '1.7x', '120M', 'Redraw, no short tenors', YP),
        ('Active - 4-qtr tenors', '4 quarters', '2.0x', '140M', 'Plan target', GP),
        ('Aggressive - prepay+short', '~3 quarters', '2.5x', '175M', 'Stretch target', BP),
        ('CEO - maximum velocity', '~2.3 quarters', '3.4x', '240M', '3-mo sales + 6-mo inv + prepay', RP),
    ]:
        ceo = 'CEO' in sc
        f_name = FONT_BOLD_C if ceo else FONT_BOLD
        f_thr = Font(bold=True, size=12 if ceo else 10, color='C00000' if ceo else '002060', name='Calibri')
        _cv(ws, r, 2, sc, f_name, pf, THIN)
        _cv(ws, r, 3, ten, FONT_BOLD, pf, THIN, ACT)
        _cv(ws, r, 4, turns, FONT_BOLD, pf, THIN, ACT)
        _cv(ws, r, 5, thr, f_thr, pf, THIN, ACT)
        _cv(ws, r, 6, feas, FONT_9_ITAL, pf, THIN, AC)
        r += 1

    r += 1
    _tr(ws, r, "RECYCLING TARGETS - SUMMARY", FONT_SECTION)
    r += 1
    for lbl, val, mult, method, pf in [
        ('Minimum (Passive)', 'ETB 105M', '1.5x', '6-month cycle, basic redraws', YP),
        ('Target (Active)', 'ETB 140M', '2.0x', '3-month cycle + active redraw', GP),
        ('Stretch (Aggressive)', 'ETB 175M', '2.5x', '+ Prepayment + shorter tenors', BP),
        (f'CEO GOAL (Maximum Velocity)', f'ETB {cfg.ceo_throughput_target / 1e6:.0f}M', f'{cfg.ceo_throughput_target / cfg.total_facility:.1f}x', 'All levers: 3-mo sales, 4-qtr LCs, prepay', RP),
    ]:
        ceo = 'CEO' in lbl
        f_lbl = FONT_BOLD_C if ceo else FONT_BOLD
        f_val = Font(bold=True, size=14 if ceo else 12, color='C00000' if ceo else '002060', name='Calibri')
        _cv(ws, r, 2, lbl, f_lbl, pf, THIN)
        _cv(ws, r, 3, val, f_val, pf, THIN, ACT)
        _cv(ws, r, 4, mult, FONT_BOLD, pf, THIN, ACT)
        _cv(ws, r, 5, method, FONT_9, pf, THIN, AWT)
        _cv(ws, r, 6, '240M!' if ceo else '', None, pf, THIN, ACT if ceo else None)
        r += 1

    r += 2
    _tr(ws, r, "OPERATIONAL PHASES - DRIVEN BY 240M TARGET", FONT_SECTION)
    r += 1
    for ph, amt, desc in [
        ('Q3 2026 Phase 1: Seed', '3.36M repaid', 'Sell opening+Reyoung stock. First repayment frees 2.95M principal. Redraw immediately as 4-quarter LC.'),
        ('Q4 2026 Phase 2: Scale', '3.36M+46.4M new', 'New LCs settle (Scott,TSM,Tinachin). Two repayments free 5.9M. Redraw supplementary 4-quarter LCs.'),
        ('2027 Phase 3: Full Cycle', '9.98M/qtr repaying', 'All 4 loans repaying. Each quarter frees ~7.5M principal. Draw 4-quarter LCs for 2nd-cycle redraws.'),
        ('2028 Phase 4: Harvest', '6.6M/qtr to 0', 'Reyoung finishes Q2, others Q4. Aggressively redraw freed capacity. Final push to 240M.'),
    ]:
        cell = ws.cell(r, 2)
        cell.value = ph
        cell.font = Font(bold=True, size=10, color="002060", name="Calibri")
        cell = ws.cell(r, 3)
        cell.value = amt
        cell.font = FONT_BOLD
        cell.alignment = ACT
        cell = ws.cell(r, 4)
        cell.value = desc
        cell.font = FONT_9
        cell.alignment = AWT
        r += 1


# ─── Low-level helpers (set styles directly, no parameter passing of style objects) ───

def _tr(ws, r, text, font, fill=None, align=None):
    """Title row: write text across B-F."""
    for c in range(2, 7):
        cell = ws.cell(r, c)
        cell.value = text if c == 2 else ''
        cell.font = font
        if fill:
            cell.fill = fill
        if align:
            cell.alignment = align


def _hdr(ws, r, c, text):
    """Header cell with dark background."""
    cell = ws.cell(r, c, text)
    cell.font = FONT_ACCENT
    cell.fill = HP
    cell.alignment = AC
    cell.border = THIN


def _cv(ws, r, c, value, font, fill, border, align=None, nf=None):
    """Cell value with direct style application."""
    cell = ws.cell(r, c, value)
    if font:
        cell.font = font
    if fill:
        cell.fill = fill
    if border:
        cell.border = border
    if align:
        cell.alignment = align
    if nf:
        cell.number_format = nf
