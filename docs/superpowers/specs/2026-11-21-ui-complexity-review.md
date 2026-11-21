# UI board (hw/ui): complexity review, DIY level

2026-11-21. Applied the same day (phase 2): R104 removed (`UI_TFT_5V` merged into `UI_5V`); C103, C104 and R105
are DNP. See *Decisions* at the end.
Level: **DIY** (PROJECT.md). J101 is an internal board-to-board interface, so it gets no protection.

Datasheets checked:
- Bourns PEC11R: contact bounce 2.0 ms max at 15 RPM, contact rating 10 mA @ 5 V. Footnote: "Devices are
  tested using standard noise reduction filters. For optimum performance, designers should use noise
  reduction filters". The suggested filter applies to A and B only: 10 k pull-up, 10 k series, 0.01 µF.
- RK3566 datasheet V1.0: GPIO3_B2 (LCD_BL, J1·18), GPIO3_C2/C3 (ENC_A/B, J1·32/33) and GPIO3_A7 (ENC_SW,
  J1·36) all come out of reset as inputs with the internal **pull-down** on (`_d`). Rpu/Rpd are 16–43 kΩ.
- Display TB147-01-08-B is an alias of GoldenMorning **GMT147-01M** (Alibaba listing "GMT147-01M (TB147-01-08-B)";
  board silkscreen GMT147SPI). The maker publishes pinout, drawing and photos at
  goldenmorninglcd.com/tft-display-module/1.47-inch-172x320-st7789-gmt147-01m/ (no PDF datasheet).
  Pinout: 1 GND, 2 VDD, 3 SCL, 4 SDA, 5 RES, 6 DC, 7 CS, 8 BL, which matches J102. The back of the module carries an
  SOT-23 LDO (U3) with C1/C2/C3/C9 and a backlight transistor Q1 with resistors marked 513 (51 k), 222 (2.2 k),
  100 (10 Ω) and 103 (10 k). Whether one of them pulls BL up is not readable from the photo.

## Core (no row needed)
| Part | Why it is core |
|---|---|
| J101 | connection to MAIN |
| J102 | display connection |
| ENC101 | the encoder |
| R101, R102, R103 | encoder pull-ups. Without them the lines sit at the SoC's reset pull-down and never go high |

## Removed (proposed)
| Part | Kind | Why it fails the test | Phase 2 action |
|---|---|---|---|
| R104 0R | service link | No build step uses it. The MAIN bring-up measures 5 V on TP6/TP7 before the Radxa is fitted. The display can be left unplugged instead. | Remove it and merge `UI_TFT_5V` into `UI_5V`; a track replaces it at PCB sync. Alternative: keep it fitted until the PCB sync |
| R105 10k | pull-down, extra | The job is "backlight off during boot", which is cosmetic. The RK3566 already holds GPIO3_B2 low from reset (internal pull-down), so this is a second part for the same job. | **DNP**. Check first, in the TB147 drawing, that BLK has no pull-up on the module; with one, R105 would only make a divider anyway |
| C103 10nF | filter, extra | Bourns' filter covers A and B only. The push switch is debounced in software (`gpio-keys`, `debounce-interval`). | **DNP** if the device tree uses gpio-keys with debounce |

## Kept
| Part | Kind | Reason it is needed at this level | What breaks or is lost without it |
|---|---|---|---|
| C101, C102 10nF | encoder filter, extra | Bourns specifies the encoder's bounce only with its noise filter in place and tells designers to fit it. Together with R101/R102 they form a near copy of that filter (10 k / 10 nF; Bourns' second 10 k series resistor is left out) | missed or double steps on A/B. Bourns' performance figures no longer apply |
| C104 100nF | decoupling at the display | **Provisional.** Decoupling is core only if the module has no input capacitor of its own (the same question as C2/C4 on MAIN). Not verifiable without the TB147 drawing | if the module carries its own LDO input capacitor: nothing → then DNP |

## Rejected (candidates not added)
| Candidate | Reason |
|---|---|
| ESD array on the encoder lines (metal shaft) | Product level. MP and C are tied to GND, and the board-to-board net is internal |
| TVS / ferrite / bulk capacitor on UI_5V | internal net, no fault source. MAIN's F1 and Q1 already guard the rack input |
| Series resistors on SPI / LCD lines | no fault at DIY level, the run is short and board-to-board |
| Level shifter to the display | logic is 3.3 V on both sides (J102 value: "逻辑3.3V") |
| Bourns' second 10 k series resistor per channel | 3 more parts. The existing RC already gives τ ≈ 100 µs |
| Use the SoC's internal pull-ups instead of R101–R103 | these are core parts. The reset state is a pull-down, and the internal 16–43 kΩ is weaker than the 10 k Bourns specifies |
| Test pads on UI | no bring-up step measures on the UI board |

## Final parts list (if all proposals are taken)
Before: 12 parts (3 connectors/encoder, 5 R, 4 C).
After: 12 footprints, 9 fitted. R104 is gone; R105 and C103 are DNP. C104 depends on the TB147 drawing.
Cost change is negligible (well under 0.10 USD per board). The change is for build simplicity, not cost.

## Build instructions that replace parts
- R104 → none; the display is simply plugged in after the MAIN 5 V check.
- R105 → device tree: drive LCD_BL low (or PWM9 at 0) until the panel is initialised.
- C103 → device tree: `gpio-keys` for ENC_SW with `debounce-interval` (default 5 ms).

## Open part-choice points (not complexity)
| Ref | Point |
|---|---|
| all except J101 | no `LCSC` / `Manufacturer` fields; `Datasheet` empty |
| C101–C103 | KEMET C0805C103K5RACTU has left the JLC snapshot (C2167345, last stock 284). Basic-part option: Samsung CL21B103KBANNNC, C1710 |
| C104 | KEMET C0805C104K5RACTU (C3018562) is extended, stock 2473. Basic: YAGEO CC0805KRX7R9BB104, C49678 |
| R101–R103, R105 | YAGEO RC0805FR-0710KL = C84376 (extended). Basic: UNI-ROYAL 0805W8F1002T5E, C17414 |
| R104 | YAGEO RC0805JR-070RL = C96345 (extended). Basic: 0805W8F0000T5E, C17477 (if R104 stays) |
| ENC101 | Bourns PEC11R-4225F-S0024, active. JLC C18198884 has only 19 in stock, so buy from Mouser/DigiKey |
| J102 | Value names the display ("TB147-01-08-B / 8针 / VDD 5V / 逻辑3.3V") but the MPN is a Samtec TSW-108-07-G-S 1×8 header (C3335496, about 1.65 USD). Make the Value the header; a generic header would be cheaper |
| R104, R105 | Value fields carry Chinese build notes ("安装", "背光默认关闭"). Move them to the sheet notes and keep plain values |
| all R/C | per-reference legacy footprints `SlewnV13_UI:R1_R0805` and so on. Switch to stock `Resistor_SMD` / `Capacitor_SMD` at PCB sync |

## Decisions (2026-11-21)
| Part | Decision | Basis |
|---|---|---|
| R104 | removed, `UI_TFT_5V` → `UI_5V` | the human chose it: a service link that no build step uses |
| C103 | DNP | the human chose it: software debounce on ENC_SW |
| C104 | DNP | the TB147/GMT147 module has its own LDO and capacitors (maker's photo). Same case as C2/C4 on MAIN |
| R105 | DNP | left to the agent by the human. Without a pull-up on the module, the RK3566 reset pull-down already holds BL low. With one, the 10 k divider would not reliably keep it off. One-minute check if wanted: power the module with BL open; if the backlight lights, the module pulls BL up |

The PCB still carries R104 and the old net `UI_TFT_5V`. That stays until the PCB sync.

## Renumbering (2026-11-21)
Closed the gap the removal left: the old **R105** (backlight pull-down, DNP) is now **R104**. It keeps its UUID
and PCB position. Every "R105" above means this part; every "R104" above means the removed 0R link.
