# MAIN Schematic Redraw Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `hw/main/Slewn_V20_MAIN.kicad_sch` with a readable, wired, block-grouped A3 schematic built from library symbols, with a netlist proven identical to today's.

**Architecture:** Small stdlib-only Python scripts in `scripts/main_sch/`. `netlist.py` proves equivalence against the backup. `fpcheck.py` compares footprint pads. `schgen.py` is a sheet writer that knows symbol pin geometry. `layout.py` declares the six blocks and writes the sheet. New library parts go in `hw/main/library/`. Tests use `unittest`, because pytest is not installed.

**Tech Stack:** Python 3.13 stdlib, `kicad-cli` 10.0.8, and `easyeda2kicad==1.0.1` in a venv at `out/venv` for the LCSC imports.

**Spec:** `docs/superpowers/specs/2026-11-20-main-schematic-redraw-design.md`

## Global Constraints
- Never edit `hw/main/Slewn_V20_MAIN.kicad_pcb`, `tools/`, or `hw/ui/`. Do not run "Update PCB from schematic".
- Before writing any file in `hw/main/`, check there is no `*.lck` file in that folder. If there is one, stop and tell the human.
- Every symbol keeps its current reference, UUID, Value, MPN and other fields. Only `Footprint` changes, per the spec's footprint map.
- Net names: keep every name except `/GND` → `GND`. `unconnected-*` single-pin nets may get new names.
- Library priority: KiCad built-in, then LCSC (`easyeda2kicad`), then other online sources, then hand-drawn.
- The sheet is A3 landscape. Every symbol position, pin and wire end is a multiple of 1.27 mm.
- New library: `hw/main/library/` containing `Slewn_MAIN.kicad_sym`, `Slewn_MAIN.pretty/`, `3dmodels/` and `SOURCES.md`. The nickname `Slewn_MAIN` is registered in `hw/main/sym-lib-table` and `fp-lib-table`. 3D model paths are written as `${KIPRJMOD}/library/3dmodels/<file>`.
- The final `tools/scripts/check.sh main` must show ERC with 0 errors and 0 warnings. Parity findings may only be footprint mismatches on the changed refs, plus net conflicts involving `GND` or `unconnected-*` nets.
- Do not commit; the human commits when they ask. Generated scratch output goes to `out/main_sch/`.

## Review Focus
1. **A wire end touching an unrelated pin or a wire mid-segment creates an unintended connection.** Expected: none. The full netlist diff in Task 6 catches it, and `test_junctions` (Task 4) checks that every T-join gets a junction.
2. **Embedded symbol copies drift from the library and produce `lib_symbol_mismatch` ERC warnings.** Expected: 0 warnings. `test_embedded_symbol_matches_library` (Task 4) checks this.
3. **Parts or text overlap, or fall off the A3 frame.** Expected: none. `test_layout_geometry` (Task 6) checks that no two symbol bounding boxes overlap, everything is inside 10–410 × 10–287 mm, and all pins are on the 1.27 mm grid.
4. **An LCSC symbol's pin numbers don't match its footprint's pads (U2/U3 EP pad 21, Q1).** Expected: an exact match. `test_symbol_pins_match_footprint_pads` (Task 3) checks this.
5. **DRC parity shows something other than the expected categories.** Expected: only the allowed set. `test_parity_only_expected` (Task 7) checks this.

---

### Task 1: Backup and netlist equivalence checker

**Files:**
- Create: `old/main-backup-2026-11-20/` (copy of `hw/main/`)
- Create: `scripts/main_sch/sexpr.py`, `scripts/main_sch/netlist.py`
- Test: `scripts/main_sch/tests/test_netlist.py`

**Interfaces:**
- Produces:
  - `sexpr.parse(text: str) -> list` (nested lists of str; quoted strings unquoted)
  - `sexpr.dump(node: list, indent: int = 0) -> str` (KiCad-style; strings quoted when needed)
  - `netlist.export(sch: Path, out: Path) -> Path` (runs `kicad-cli sch export netlist --format kicadsexpr`)
  - `netlist.load(net_path: Path) -> Netlist`, where `Netlist` is a dataclass with:
    - `comps: dict[str, dict[str, str]]` (ref → {value, footprint, MPN, …})
    - `nets: dict[str, frozenset[tuple[str, str]]]` (net name → {(ref, pin)})
  - `netlist.diff(old: Netlist, new: Netlist, renames: dict[str, str] = {"/GND": "GND"}) -> list[str]`
    - Returns human-readable problems; an empty list means equivalent.
    - Compares the partition of (ref, pin) into nets, net names except `unconnected-*` (after applying `renames`), and every comp field except `footprint` and `Footprint`.
  - `netlist.footprint_changes(old, new) -> dict[str, tuple[str, str]]`
  - `netlist.pin_net_mismatches(old, new, refs: set[str], renames=...) -> list[str]` (per-pin net-name check limited to `refs`; `unconnected-*` ignored)
  - CLI: `python3 scripts/main_sch/netlist.py OLD.kicad_sch NEW.kicad_sch` prints the diff and footprint changes, and exits 1 if the diff is non-empty.

- [ ] **Step 1: Back up.** Run `ls hw/main/*.lck 2>/dev/null` (expect nothing), then `cp -a hw/main old/main-backup-2026-11-20`. Check with `diff -r hw/main old/main-backup-2026-11-20` (expect no output).
- [ ] **Step 2: Write the failing tests** in `test_netlist.py`. A `setUpClass` exports `old/main-backup-2026-11-20/Slewn_V20_MAIN.kicad_sch` to `out/main_sch/old.net`.
  - `test_identical_is_empty`: `diff(old, old) == []`
  - `test_counts`: `len(old.comps) == 39`, `old.nets["/GND"]` contains `("J3","3")` and `("U2","21")`, and `old.nets["/5V_SAFE"]` contains `("J1","2")`
  - `test_moved_pin_detected`: move `("R10","2")` from `/OV2` into `/OV3` on a copy; `diff` is non-empty
  - `test_gnd_rename_allowed`: rename `/GND` to `GND` on a copy; `diff == []`
  - `test_unconnected_rename_allowed`: rename `unconnected-(J1-NC-Pad3)` to `unconnected-(J1-Pin_3-Pad3)`; `diff == []`
  - `test_value_change_detected`: set `R12` value to `"1k"`; the `diff` contains `"R12"`
  - `test_footprint_change_reported_not_diffed`: change the C1 footprint; `diff == []` and `footprint_changes` returns `{"C1": (...)}`
  - `test_sexpr_roundtrip`: `parse(dump(parse(t))) == parse(t)` for the backup `.kicad_sch` text
- [ ] **Step 3:** Run `python3 -m unittest discover -s scripts/main_sch/tests -v`. Expect a FAIL or ImportError.
- [ ] **Step 4: Implement `sexpr.py` and `netlist.py`.** Use the tokenizer regex `\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+`, unescaping `\"` and `\\`.
- [ ] **Step 5:** Run the tests again. Expect all to PASS.

### Task 2: Footprints into the new library

**Files:**
- Create: `hw/main/library/Slewn_MAIN.pretty/{J1_GPIO40,J3_IDC10,U1_Waveshare33x16}.kicad_mod`, plus J2 and L1 (see Step 4), and `hw/main/library/3dmodels/*`
- Create: `scripts/main_sch/fpcheck.py`
- Modify: `hw/main/fp-lib-table` (add `Slewn_MAIN` → `${KIPRJMOD}/library/Slewn_MAIN.pretty`)
- Test: `scripts/main_sch/tests/test_fpcheck.py`

**Interfaces:**
- Produces:
  - `fpcheck.pads(path: Path) -> dict[str, list[tuple]]` (pad number → [(x, y, w, h, drill)])
  - `fpcheck.same_pads(a: Path, b: Path) -> bool`
  - `FOOTPRINT_MAP: dict[str, str]` in `scripts/main_sch/parts.py`, the ref → footprint lib ID used by Task 6:
    - C1, C2: `Capacitor_SMD:C_1210_3225Metric`
    - D1: `Diode_SMD:D_SOD-123`
    - F1: `Fuse:Fuse_1206_3216Metric`
    - Q1: `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`
    - R1: `Resistor_SMD:R_0805_2012Metric`
    - J1: `Slewn_MAIN:J1_GPIO40`
    - J3: `Slewn_MAIN:J3_IDC10`
    - U1: `Slewn_MAIN:U1_Waveshare33x16`
    - J2, L1: decided in Step 4
    - Every other ref keeps its current footprint.

- [ ] **Step 1: Write the failing tests.**
  - `test_identical`: `same_pads(Libs/SlewnV13.pretty/C1_C1210, <KiCad>/Capacitor_SMD.pretty/C_1210_3225Metric)` is True
  - `test_rotated_differs`: J1_GPIO40 vs `PinHeader_2x20_P2.54mm_Vertical` is False
  - `test_drill_differs`: J3_IDC10 vs `IDC-Header_2x05_P2.54mm_Vertical` is False
  - `test_map_swaps_are_identical`: for every ref in `FOOTPRINT_MAP` whose target is a stock KiCad footprint, `same_pads(current, target)` is True. The current footprint is read from `old.comps`, and the KiCad footprint dir is `/usr/share/kicad/footprints`.
  - `test_library_copies_identical`: each `Slewn_MAIN.pretty` file has the same pads as its source in `Libs/`.
  - `test_models_resolve`: every `(model ...)` path in `Slewn_MAIN.pretty` starts with `${KIPRJMOD}/library/3dmodels/`, and the file exists.
- [ ] **Step 2:** Run the tests. Expect them to FAIL.
- [ ] **Step 3: Implement `fpcheck.py` and `parts.py`.** Copy the J1, J3 and U1 footprints and their STEP models, then rewrite the model paths.
- [ ] **Step 4: J2 and L1.**
  - Create `out/venv` and `pip install easyeda2kicad==1.0.1` into it.
  - Look up the LCSC codes for `KH-2.54PH90-1X14P-L13.8` and `74437324022` with pcbparts `jlc_get_parts`.
  - Import each footprint into `out/main_sch/lcsc/` with `out/venv/bin/easyeda2kicad --lcsc_id=<C…> --footprint --3d --output out/main_sch/lcsc/lcsc`.
  - If `same_pads(lcsc, current)` is True, use the LCSC footprint and its model. Otherwise copy the current `Libs/` footprint.
  - In both cases the file goes into `Slewn_MAIN.pretty`, and the outcome is recorded in `FOOTPRINT_MAP` and in `SOURCES.md`.
- [ ] **Step 5:** Run the tests. Expect them to PASS.

### Task 3: Symbols into the new library

**Files:**
- Create: `hw/main/library/Slewn_MAIN.kicad_sym` (AO4407A and TPS25940LRVCR from LCSC; a hand-drawn `Waveshare_DC536_5V`), `hw/main/library/SOURCES.md`
- Modify: `hw/main/sym-lib-table` (add `Slewn_MAIN` → `${KIPRJMOD}/library/Slewn_MAIN.kicad_sym`)
- Modify: `scripts/main_sch/parts.py` (add `SYMBOL_MAP`)
- Test: `scripts/main_sch/tests/test_symbols.py`

**Interfaces:**
- Consumes: `FOOTPRINT_MAP`, `fpcheck.pads`
- Produces:
  - `SYMBOL_MAP: dict[str, str]`, ref → lib ID, exactly the spec's symbol map:
    - Q1: `Slewn_MAIN:AO4407A`
    - U2, U3: `Slewn_MAIN:TPS25940LRVCR`
    - U1: `Slewn_MAIN:Waveshare_DC536_5V`
    - J1: `Connector_Generic:Conn_02x20_Odd_Even`
    - J2: `Connector_Generic:Conn_01x14`
    - J3: `Connector_Generic:Conn_02x05_Odd_Even`
    - D2: `Diode:SMAJ12A`
    - …and so on for the rest of the spec's table
  - `parts.symbol_pins(lib_id: str) -> dict[str, str]` (pin number → pin name), reading KiCad libs from `/usr/share/kicad/symbols` and `Slewn_MAIN.kicad_sym`

- [ ] **Step 1: Write the failing tests.**
  - `test_symbol_pins_match_footprint_pads`: for all 39 refs, `set(symbol_pins(SYMBOL_MAP[ref])) == set(pads(FOOTPRINT_MAP[ref] resolved))`. Pads with an empty number (mechanical) are ignored, and a pad number that appears several times counts once.
  - `test_all_refs_mapped`: `set(SYMBOL_MAP) == set(old.comps)`
  - `test_u1_pins`: `symbol_pins("Slewn_MAIN:Waveshare_DC536_5V")` keys are `{I1,I2,I3,I4,O1,O2,O3,O4,O5,O6}`. I1 and I2 are named GND, I3 and I4 VIN, O1–O3 GND, O4–O6 5V. Pin types: VIN `power_in`, 5V `power_out`, GND `power_in`.
  - `test_tps25940_names`: pin 15 is OVP, 17 ILIM, 18 dVdT, 14 EN/UVLO, and 21 exists. Names are compared case-insensitively.
- [ ] **Step 2:** Run the tests. Expect them to FAIL.
- [ ] **Step 3: Import from LCSC.**
  - Look up the LCSC codes for AO4407A and TPS25940LRVCR with pcbparts.
  - Run `easyeda2kicad --symbol` into `out/main_sch/lcsc/`.
  - Copy the two symbols into `Slewn_MAIN.kicad_sym`, renamed to the lib IDs above, with an `LCSC` property added.
  - If an import lacks EP pin 21, or misnumbers it, add or fix the pin by hand and note that in `SOURCES.md`.
- [ ] **Step 4: Draw `Waveshare_DC536_5V`.**
  - A rectangle, VIN and GND-in on the left, 5V and GND-out on the right.
  - Same-named pins stacked, one visible, the others `hide` (KiCad stacked pins).
  - All pins on the 2.54 mm grid.
- [ ] **Step 5: Write `SOURCES.md`.** One row per item: what it is, where it came from (LCSC code and URL, KiCad 10.0.8, or hand-drawn), its licence, and any edits made. Carry over the KiCad CC-BY-SA notice from `Libs/LICENSE-SOURCES.txt` for the copied footprints and models.
- [ ] **Step 6:** Run the tests. Expect them to PASS. Also run `kicad-cli sym upgrade --force hw/main/library/Slewn_MAIN.kicad_sym -o out/main_sch/symcheck.kicad_sym` and expect exit code 0, which proves the file parses.

### Task 4: Sheet writer (`schgen.py`)

**Files:**
- Create: `scripts/main_sch/schgen.py`
- Test: `scripts/main_sch/tests/test_schgen.py`

**Interfaces:**
- Consumes: `sexpr`, `parts.SYMBOL_MAP`, `parts.FOOTPRINT_MAP`
- Produces: class `Sheet(old_sch: Path, paper="A3")`
  - Reads the title block and, per ref, the old instance (`uuid` and all properties).
  - `place(ref, x, y, rot=0, mirror=None) -> None`
    - The lib ID comes from `SYMBOL_MAP` and the footprint from `FOOTPRINT_MAP`.
    - The UUID, Value and other properties come from the old instance.
    - Reference and Value text are placed beside the body.
  - `pin(ref, num) -> tuple[float, float]` (sheet coordinate of the pin's connection point)
  - `wire(*pts)`: an orthogonal polyline. A point is either `(x, y)` or `"REF.PIN"`.
  - `label(net, at, rot=0)` (local label)
  - `power(name, at, rot=0)`: `power:GND` or `power:PWR_FLAG`. Each gets a fresh UUID and a `#PWR0n` / `#FLG0n` reference.
  - `nc(ref, num)`
  - `box(title, x1, y1, x2, y2)` (graphic rectangle plus a title text in the top-left corner)
  - `note(text, at, size=1.8)`
  - `write(path: Path)`
    - Embeds every used `lib_symbols` entry verbatim from its library.
    - Auto-adds junctions wherever a wire end lands on the interior of another wire, or three or more wire ends or pins meet.
    - Writes `(instances (project "Slewn_V20_MAIN" (path "/<root uuid>" (reference ..) (unit 1))))` with the old root sheet UUID.
- Pin transform: library coordinates are Y-up and sheet coordinates are Y-down. Take the library pin `(px, py)`:
  1. Apply the mirror (x: `py = -py`; y: `px = -px`).
  2. Rotate CCW by `rot`.
  3. The sheet position is `(X + rx, Y - ry)`.
  4. Round to 0.01.

- [ ] **Step 1: Write the failing tests.**
  - `test_pin_transform`: R10 placed at (101.6, 101.6) with rot 0 gives `pin("R10","1") == (101.6, 97.79)`. With rot 90, it gives `(97.79, 101.6)`.
  - `test_roundtrip_minimal`:
    - Sheet with R10, R11, a wire `"R10.2"` to `"R11.1"`, label `/OV2`-equivalent `OV2` on that wire, and `power("GND")` at R11.2.
    - Write it to `out/main_sch/t/t.kicad_sch` with a copy of the project file, then export the netlist.
    - Expect net `/OV2` = {(R10,2), (R11,1)}, net `GND` ∋ (R11,2), and R10's UUID equal to the old one.
  - `test_junctions`: a wire T-joining another wire's middle produces exactly one `(junction` at that point.
  - `test_embedded_symbol_matches_library`: write a sheet with one part per distinct lib ID and run `kicad-cli sch erc --format json`. Expect zero violations of type `lib_symbol_mismatch` or `lib_symbol_issues`.
- [ ] **Step 2:** Run the tests. Expect them to FAIL.
- [ ] **Step 3: Implement `schgen.py`.**
- [ ] **Step 4:** Run the tests. Expect them to PASS.

### Task 5: Blocks 1–3 (rack input, 12 V eFuse, input filter)

**Files:**
- Create: `scripts/main_sch/layout.py`. It contains block functions `block_rack_input(s: Sheet, x0, y0)`, `block_efuse12(...)` and `block_filter(...)`, plus `build(out: Path, blocks=ALL)`.
- Test: `scripts/main_sch/tests/test_layout.py`

**Interfaces:**
- Consumes: `Sheet`, `netlist.pin_net_mismatches`
- Produces: `layout.build(out: Path, blocks: list[str] | None = None) -> Path`, with block keys `rack`, `efuse12`, `filter`, `buck`, `efuse5`, `headers`

Block contents (from the spec):
- **rack:** J3 (pins 9 and 10 to RACK_12V; 3–8 to GND; 1 and 2 NC) → F1 → Q1 (D=VIN_FUSED in, S=VIN_PROTECTED out). Gate: D1 between GATE and VIN_PROTECTED, R1 from GATE to GND. Then D2, C1, C12, TP1 and TP7 on VIN_PROTECTED and GND.
- **efuse12:** U2 with IN, EN/UVLO = VIN_PROTECTED; R10 and R11 divider to OVP (OV2); R12 on ILIM (IL2); C10 on dVdT (SS2); DEVSLP and PGTH to GND; PGOOD, IMON and FLT NC. OUT = V12_LIMITED with C3, D3 (cathode on V12_LIMITED) and TP2.
- **filter:** L1 from V12_LIMITED to VIN_FILTERED; C4; R18 → DAMP → C5(+), C5(−) to GND; TP3.
- Power runs left to right as wires, with each named net labelled once inside its block. Box titles: `1 RACK INPUT`, `2 12V EFUSE`, `3 INPUT FILTER`.

- [ ] **Step 1: Write the failing test** `test_blocks_1_3`. Build with `["rack","efuse12","filter"]` to `out/main_sch/partial/`, export the netlist, and check that `pin_net_mismatches(old, new, refs={J3,F1,Q1,D1,R1,D2,C1,C12,TP1,TP7,U2,R10,R11,R12,C10,C3,D3,TP2,L1,C4,R18,C5,TP3}) == []`.
- [ ] **Step 2:** Run the test. Expect it to FAIL.
- [ ] **Step 3: Implement the three block functions.**
- [ ] **Step 4:** Run the test. Expect it to PASS. Render with the KiCad MCP `get_schematic_view` and check that the three boxes read left to right with nothing overlapping.

### Task 6: Blocks 4–6, notes, full sheet

**Files:**
- Modify: `scripts/main_sch/layout.py` (add `block_buck`, `block_efuse5` and `block_headers`, plus the notes)
- Test: `scripts/main_sch/tests/test_layout.py`

Block contents:
- **buck:** U1 with VIN = VIN_FILTERED, 5V = BUCK_RAW, GND; TP4.
- **efuse5:** R20 (BUCK_RAW → EF_IN5), then U3 with IN and EN/UVLO = EF_IN5. R14 and R15 to OVP (OV3), R16 on ILIM (IL3), C11 on dVdT (SS3), C6 and C13 on EF_IN5, TP5. OUT = 5V_SAFE with C2, D4 and TP6.
- **headers:** J1 and J2. Power pins are wired to 5V_SAFE, 3V3 and GND. SPI_CLK, SPI_MOSI, LCD_CS, LCD_DC, LCD_RST, LCD_BL, ENC_A, ENC_B, ENC_SW and 3V3 go as labels on short stubs. All J1 NC pins get `nc()`.

Notes: carry over these three original texts verbatim:
1. `MAIN / J2 接 UI 的 J101，按 1 至 14 脚逐一对应。正面装原厂 90° 公排针，插向面板。`
2. `R20 open during first bring-up` (from title-block comment 2)
3. `BENCH TEST POINTS | NO SBC DURING FAULT TESTS`

Keep the title block unchanged. Add `PWR_FLAG` on GND and on RACK_12V only if ERC asks for them.

- [ ] **Step 1: Write the failing tests.**
  - `test_full_equivalence`: `build(out/main_sch/full/Slewn_V20_MAIN.kicad_sch)` followed by `netlist.diff(old, new) == []`. Also `footprint_changes(old, new).keys() == {refs whose FOOTPRINT_MAP target differs from old}`.
  - `test_layout_geometry`:
    - From the written file, compute each symbol's bounding box from its embedded graphics, transformed.
    - No two boxes intersect.
    - All boxes lie within x 10–410 mm and y 10–287 mm.
    - Every symbol `at` and every wire point is a multiple of 1.27 within 0.005.
  - `test_erc_clean`: `kicad-cli sch erc --format json --severity-all` on the full sheet. Expect 0 errors and 0 warnings.
- [ ] **Step 2:** Run the tests. Expect them to FAIL.
- [ ] **Step 3: Implement the remaining blocks and the notes.**
- [ ] **Step 4:** Run the tests. Expect them to PASS.
- [ ] **Step 5: Visual review.** Run `get_schematic_view` at 2000×1400 and check:
  - six titled boxes, read left to right in power-flow order;
  - no text over wires or symbols;
  - labels readable.
  Fix any problems and rerun Step 4.

### Task 7: Install into the project and final checks

**Files:**
- Modify: `hw/main/Slewn_V20_MAIN.kicad_sch` (replaced by the generated file)
- Test: `scripts/main_sch/tests/test_install.py`

- [ ] **Step 1: Write the failing test** `test_parity_only_expected`:
  - Run `tools/scripts/check.sh main` and read `out/reports/` for the main DRC JSON.
  - Every parity item must be either a footprint mismatch on a ref in `footprint_changes`, or a net conflict whose text mentions `GND` or `unconnected-`.
  - The main ERC report must have 0 errors and 0 warnings.
- [ ] **Step 2:** Run the test. Expect it to FAIL, because the project still holds the old sheet.
- [ ] **Step 3: Install the new sheet.**
  - Check that `ls hw/main/*.lck` returns nothing.
  - Copy `out/main_sch/full/Slewn_V20_MAIN.kicad_sch` over `hw/main/Slewn_V20_MAIN.kicad_sch`.
  - Run `git diff --stat hw/main/Slewn_V20_MAIN.kicad_pcb` and expect empty output.
- [ ] **Step 4:** Run the full suite with `python3 -m unittest discover -s scripts/main_sch/tests -v`. Expect all tests to PASS.
- [ ] **Step 5: Sanity check.** Run `python3 .claude/skills/kicad/scripts/analyze_schematic.py hw/main/Slewn_V20_MAIN.kicad_sch` (output to `out/main_sch/`). Read the findings and report anything that contradicts the old design's behaviour. There should be none, because the circuit is identical.
- [ ] **Step 6: Report to the human.**
  - The files changed: `hw/main/Slewn_V20_MAIN.kicad_sch`, `hw/main/sym-lib-table`, `hw/main/fp-lib-table` and `hw/main/library/`. Tell them to reload these in KiCad.
  - The footprint changes list, and the J2/L1 outcome.
  - The expected parity findings, which clear at the PCB sync.
  - An offer to commit.
