"""Display two lines on the Grove 16x2 LCD (White on Blue) over I2C."""

import argparse
import sys
import time

I2C_BUS = 1
LCD_ADDRESS = 0x3E
COMMAND = 0x80
CHARACTER = 0x40
ROW_STARTS = (0x80, 0xC0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--line1", default="NatureMatch", help="Top row (default: NatureMatch)")
    parser.add_argument("--line2", default="1234567890123456", help="Bottom row (default: %(default)s)")
    args = parser.parse_args(argv)
    lines = (args.line1, args.line2)
    for row, line in enumerate(lines, start=1):
        if len(line) > 16 or any(not " " <= char <= "~" for char in line):
            parser.error(f"--line{row} must contain at most 16 printable ASCII characters")

    try:
        from smbus2 import SMBus
    except ImportError:
        print("Missing smbus2. Install it with: python -m pip install smbus2", file=sys.stderr)
        return 1

    try:
        with SMBus(I2C_BUS) as bus:
            # Use the JHD1802 command framing from Seeed's grove.py reference.
            bus.write_byte_data(LCD_ADDRESS, COMMAND, 0x02)  # Return home
            time.sleep(0.1)
            bus.write_byte_data(LCD_ADDRESS, COMMAND, 0x28)  # Two-line mode
            bus.write_byte_data(LCD_ADDRESS, COMMAND, 0x0C)  # Display on, cursor off
            bus.write_byte_data(LCD_ADDRESS, COMMAND, 0x01)  # Clear old text
            time.sleep(0.002)
            bus.write_byte_data(LCD_ADDRESS, COMMAND, 0x06)  # Advance cursor after each character

            for row_start, line in zip(ROW_STARTS, lines):
                bus.write_byte_data(LCD_ADDRESS, COMMAND, row_start)
                for char in line:
                    bus.write_byte_data(LCD_ADDRESS, CHARACTER, ord(char))
    except OSError as error:
        print(
            f"LCD write failed on /dev/i2c-{I2C_BUS} at {LCD_ADDRESS:#04x}: {error}",
            file=sys.stderr,
        )
        print(
            "Check that I2C is enabled and the LCD is connected to a Grove I2C socket.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130

    print(f"Text sent. Check the display for {args.line1!r} above {args.line2!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
