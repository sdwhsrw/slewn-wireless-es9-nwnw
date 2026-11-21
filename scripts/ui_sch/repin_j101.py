"""Give UI connector J101 the pin order agreed on 2026-11-21 (it mates 1:1 with MAIN J2).

Pins 1-8 follow the display J102's own order, 9-14 are the encoder block. Only the 14 net labels at J101 and
the pin names of its symbol (embedded copy and Libs/SlewnV13_UI.kicad_sym) change; everything else stays.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "hw" / "ui"
SCH = UI / "Slewn_V20_UI.kicad_sch"
LIB = UI / "Libs" / "SlewnV13_UI.kicad_sym"

ORDER = ["GND", "5V", "SPI_CLK", "SPI_MOSI", "LCD_RST", "LCD_DC", "LCD_CS", "LCD_BL",
         "GND", "3V3", "ENC_A", "ENC_B", "ENC_SW", "GND"]
LABEL_X, PIN1_Y, PITCH = 33.02, 43.18, 2.54          # J101's labels sit in one column, pin 1 at the top
PIN_RE = re.compile(r'(\(name\n\s+")([^"]*)("(?:\s+\(effects\s+\(font\s+\(size [^)]*\)\)\)\))?\s+\(number\n\s+")(\d+)(")')


def rename_pins(text: str, start: str, end: str) -> str:
    """Set pin names inside the symbol block that begins at `start` and ends before `end`."""
    a = text.index(start)
    b = text.index(end, a + len(start))
    block = PIN_RE.sub(lambda m: m[1] + ORDER[int(m[4]) - 1] + m[3] + m[4] + m[5], text[a:b])
    return text[:a] + block + text[b:]


def relabel(text: str) -> str:
    def one(m):
        y = float(m[3])
        n = round((y - PIN1_Y) / PITCH)
        if float(m[2]) != LABEL_X or not 0 <= n < 14 or abs(PIN1_Y + n * PITCH - y) > 0.01:
            return m[0]
        return m[0].replace(f'"{m[1]}"', f'"UI_{ORDER[n]}"', 1)
    return re.sub(r'\(label\n\s+"([^"]+)"\n\s+\(at ([\d.]+) ([\d.]+) 0\)', one, text)


def main() -> None:
    sch = SCH.read_text()
    sch = rename_pins(sch, '"SlewnV13_UI:J1"', '"SlewnV13_UI:J2"')
    sch = relabel(sch)
    sch = sch.replace("R20 open during first bring-up.", "check 5 V before fitting the Radxa.")
    SCH.write_text(sch)
    lib = LIB.read_text()
    LIB.write_text(rename_pins(lib, '"J1"', '"J2"'))


if __name__ == "__main__":
    sys.exit(main())
