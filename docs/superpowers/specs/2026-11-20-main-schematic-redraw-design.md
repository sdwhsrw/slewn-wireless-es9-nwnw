# MAIN schematic redraw — design

Date: 2026-11-20 · Board: `hw/main` (Slewn_V20_MAIN) · KiCad 10.0.8

## Intent
The MAIN schematic is unreadable: all 39 symbols are home-made rectangles whose pins are named after
nets, joined only by net labels, scattered over the sheet. Redraw it so a person can follow the
circuit, using real library symbols, with the circuit itself unchanged. The PCB is not touched and is
not synced in this work.

## Goals
- Same circuit: every part, every pin-to-net connection, every value and MPN as today.
- Library symbols chosen in this order: (1) KiCad 10 built-in, (2) LCSC/EasyEDA via `easyeda2kicad`
  (the converter behind the Import-LIB-KiCad-Plugin), (3) other online sources, (4) drawn by hand only
  when nothing exists.
- Footprints (human's choice **B**): switch to standard KiCad (or LCSC) footprints where they exist.
- One A3 sheet, circuit drawn with real wires, grouped into boxed, titled functional blocks.
- All new symbols, footprints and 3D models in one new folder inside the project.
- A backup of the project before any edit.

## Non-goals
- No PCB edits, no "Update PCB from schematic".
- No component value, MPN or topology changes, even where a review would suggest one.
- No UI board (`hw/ui`) work.
- Old `Libs/` folder is not deleted (the PCB still references it until the sync).

## Anti-goals
- A redraw whose netlist differs from today's in any connection.
- A footprint swap that would silently move pads on the board at sync time.

## Constraints
- Files must open in KiCad 10 on the host; nothing under `tools/` is edited.
- No `.lck` file may sit next to the files edited.
- Each symbol instance keeps its current UUID and reference, so the later sync re-links every
  footprint by path.
- `tools/scripts/check.sh main`: ERC must report 0 errors / 0 warnings as today. DRC parity *will*
  report schematic-vs-PCB differences (footprint lib IDs, the GND net name, and renamed `unconnected-*`
  nets, see Net names); those are expected until the sync and must be the only parity findings.

## Approaches
**Layout.** (a) One A3 sheet with boxed groups — **picked**: the circuit is 39 symbols and reads as one
power path; symbol paths stay flat so the sync re-links by UUID. (b) Hierarchical sheets per block —
rejected: six pages for one page of circuit, and moving symbols into sub-sheets changes their paths,
forcing a re-link by reference at sync.

**Footprints.** (A) keep the PCB's current footprints — rejected by the human. (B) standard/LCSC
footprints where they exist — **picked**.

**How the file is produced** (my call). A Python generator writes the `.kicad_sch` (symbols, wires,
junctions, labels, group boxes) from a declarative description; a second script proves netlist
equivalence. Rejected: placing parts one by one through the KiCad MCP server (hundreds of calls, hard to
keep on grid, no equivalence proof) and hand-editing the file.

## Backup (my call)
Copy `hw/main/` to `old/main-backup-2026-11-20/` before the first edit (outside `hw/`, so `check.sh`
ignores it). Committing the clean-up branch as an extra restore point is offered to the human, not done
unasked.

## New library folder (my call)
`hw/main/library/`:
- `Slewn_MAIN.kicad_sym` — every non-built-in symbol (LCSC imports, hand-drawn U1).
- `Slewn_MAIN.pretty/` — every footprint that is not a stock KiCad footprint.
- `3dmodels/` — models for those footprints, referenced as `${KIPRJMOD}/library/3dmodels/...`.
- `SOURCES.md` — origin and licence of each item (LCSC part numbers, KiCad CC-BY-SA notice carried over).
Registered in the project `sym-lib-table` / `fp-lib-table` as `Slewn_MAIN`. Built-in symbols are used from
the KiCad libraries directly (the schematic embeds a copy, as KiCad always does).

## Symbol map
| Ref | Part | Symbol |
|---|---|---|
| R1, R10–R12, R14–R16, R18, R20 | resistors | `Device:R` |
| C1–C4, C6, C10–C13 | ceramic caps | `Device:C` |
| C5 | 47 µF polar | `Device:C_Polarized` |
| L1 | 2.2 µH | `Device:L` |
| D1 | BZT52C12 | `Device:D_Zener` |
| D2 | SMAJ12A | `Diode:SMAJ12A` |
| D3, D4 | B340A | `Device:D_Schottky` |
| F1 | 2 A fuse | `Device:Fuse` |
| Q1 | AO4407A SO-8 P-MOS | LCSC import (8 pins, S=1–3, G=4, D=5–8) |
| U2, U3 | TPS25940LRVCR | LCSC import (21 pins incl. EP) |
| U1 | Waveshare DC5-36 → 5 V module | hand-drawn: VIN, GND in, 5V out, GND out, pins I1–I4 / O1–O6 |
| J1 | Radxa ZERO 3W 40-pin | `Connector_Generic:Conn_02x20_Odd_Even` |
| J2 | 14-pin to UI | `Connector_Generic:Conn_01x14` |
| J3 | Eurorack 10-pin power | `Connector_Generic:Conn_02x05_Odd_Even` |
| TP1–TP7 | test pads | `Connector:TestPoint` |
| ground | — | `power:GND` (+ `power:PWR_FLAG` where ERC needs it) |

Any imported symbol's pin numbers are checked against its footprint's pad numbers before use.

## Footprint map (rule: swap only if every pad is identical; otherwise keep the current one, copy it into `Slewn_MAIN.pretty`, and list it)
| Ref | Current | Outcome |
|---|---|---|
| C1, C2 | SlewnV13:C*_C1210 | → `Capacitor_SMD:C_1210_3225Metric` (pads identical) |
| D1 | SlewnV13:D1_SOD123 | → `Diode_SMD:D_SOD-123` (identical) |
| F1 | SlewnV13:F1_FUSE1206 | → `Fuse:Fuse_1206_3216Metric` (identical) |
| Q1 | SlewnV13:Q1_SO8 | → `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm` (identical) |
| R1 | SlewnV13:R1_R0805 | → `Resistor_SMD:R_0805_2012Metric` (identical) |
| J1 | SlewnV13:J1_GPIO40 | **keep** — it is the 2×20 header rotated 90°; a swap would put the Radxa pins in the wrong place |
| J3 | SlewnV13:J3_IDC10 | **keep** — deliberate 1.1 mm drill / 1.9 mm pad vs stock 1.0 / 1.7 |
| J2 | Kinghelm:KH-2.54PH90-1X14P | try LCSC footprint; stock has 1.0 vs 1.02 mm drill → keep unless LCSC is identical |
| L1 | V16:WE_LHMI_74437324022 | no stock Würth LHMI footprint; try LCSC; keep unless identical |
| U1 | SlewnV13:U1_Waveshare33x16 | **keep** — no library has it |
| others | already stock KiCad | unchanged |

Kept footprints move into `Slewn_MAIN.pretty` (same pads, same 3D models), so the schematic no longer
points at `Libs/`.

## Sheet layout
A3 landscape, 1.27 mm grid, all pins on grid. Power flows left → right, one titled box per block:

```
┌ 1 RACK INPUT ─────┐┌ 2 12V eFUSE ─┐┌ 3 INPUT FILTER ┐┌ 4 5V BUCK ─┐┌ 5 5V eFUSE ──┐┌ 6 RADXA / UI ─┐
│ J3 → F1 → Q1      ││ U2           ││ L1 → C4        ││ U1         ││ R20 → U3     ││ J1            │
│ D1 R1 (gate)      ││ R10/R11 OVP  ││ R18 + C5 damp  ││ TP4        ││ R14/R15 OVP  ││ J2            │
│ D2 TVS, C1 C12    ││ R12 ILIM     ││ TP3            ││            ││ R16 ILIM C11 ││ (SPI/LCD/ENC  │
│ TP1               ││ C10 C3 D3 TP2││                ││            ││ C6 C13 C2 D4 ││  net labels)  │
└───────────────────┘└──────────────┘└────────────────┘└────────────┘│ TP5 TP6      │└───────────────┘
                                                                      └──────────────┘
TP7 (GND) with block 1. Notes block: the existing sheet notes (J2 ↔ UI J101 1:1, R20 open at first
bring-up, bench test points / no SBC during fault tests). Title block unchanged.
```
- Wires within a block; between blocks the power nets run as wires along the power path, with a net
  label naming each one (VIN_PROTECTED, V12_LIMITED, VIN_FILTERED, BUCK_RAW, EF_IN5, 5V_SAFE).
- Signals between J1 and J2 (SPI_CLK, SPI_MOSI, LCD_*, ENC_*, 3V3) as net labels on short stubs.
- Unused pins (J1 NCs, J3 pins 1–2, U2/U3 PGOOD/IMON/FLT) get no-connect flags.
- Net names: every existing name kept except the ground net, which becomes `GND` (power symbol)
  instead of `/GND`. Accepted: this renames one net at sync.
- Unconnected-pin nets (my call): KiCad names these after the pin name, e.g. `unconnected-(J1-NC-Pad3)`.
  Stock connector symbols name those pins `Pin_3` etc., and the LCSC TPS25940 symbol may rename PGOOD /
  IMON / FLT, so up to 28 single-pin `unconnected-*` nets get new names. Accepted as expected findings
  (they carry no copper connection and clear at the sync) rather than cloning stock symbols just to keep
  `NC` pin names.

## Verification
1. Netlist equivalence: export old and new netlists; for every (ref, pin) the set of pins sharing its
   net must be identical; refs, values, MPNs identical; differences allowed only in net names (`/GND`→`GND`)
   and `unconnected-*` single-pin nets, and footprint fields per the map above.
2. `tools/scripts/check.sh main`: ERC 0/0; parity findings limited to the expected ones.
3. Render the sheet and check it visually: no overlapping text, nothing off-grid, boxes readable.
4. Run kicad-happy `analyze_schematic.py` on the new file as a sanity read.

## Tooling
`easyeda2kicad` is not installed in the container; it is pip-installed into a user/virtual env at
build time (nothing under `tools/` changes). If LCSC has no usable symbol for a part, fall through the
symbol priority list.

## Left to the builder
Exact coordinates, wire routing within blocks, symbol orientation, text sizes, LCSC part codes for
Q1/U2/U3/J2/L1 (look up via the pcbparts MCP server).
