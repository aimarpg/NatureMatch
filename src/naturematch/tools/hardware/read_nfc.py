"""Test an M5Stack Unit RFID2 (WS1850S, MFRC522-compatible) reader over I2C.

Polls for ISO 14443-A cards/tags and prints one JSON line per attempt. Raw card
identifiers are never printed: each UID is replaced by an HMAC reference keyed
with a random per-run secret, so repeat taps can be recognised within one run but
not linked across runs. This is a hardware diagnostic only; it creates no
check-in sessions and is not integrated with station acquisition or storage.
The unit is powered from 5 V: confirm its I2C pull-up voltage is safe for the
Pi's 3.3 V pins, and confirm wiring and Pi 5 I2C setup, before use.
"""
import argparse
import hashlib
import hmac
import json
import math
import secrets
import sys
import time
from datetime import UTC, datetime

MODEL = "M5Stack Unit RFID2 (WS1850S, MFRC522-compatible)"

# MFRC522 registers and commands (NXP MFRC522 datasheet; WS1850S is register-compatible).
COMMAND, COM_IRQ, ERROR, FIFO_DATA, FIFO_LEVEL = 0x01, 0x04, 0x06, 0x09, 0x0A
CONTROL, BIT_FRAMING, COLL, MODE, TX_MODE, RX_MODE = 0x0C, 0x0D, 0x0E, 0x11, 0x12, 0x13
TX_CONTROL, TX_ASK, MOD_WIDTH = 0x14, 0x15, 0x24
T_MODE, T_PRESCALER, T_RELOAD_H, T_RELOAD_L, VERSION = 0x2A, 0x2B, 0x2C, 0x2D, 0x37
CMD_IDLE, CMD_TRANSCEIVE, CMD_SOFT_RESET = 0x00, 0x0C, 0x0F
IRQ_TIMER, IRQ_IDLE, IRQ_RX = 0x01, 0x10, 0x20
ERR_PROTOCOL_PARITY_OVERFLOW, ERR_COLLISION = 0x13, 0x08

# ISO 14443-3 type A card commands.
PICC_WUPA, PICC_HLTA = 0x52, 0x50
CASCADE_LEVELS = (0x93, 0x95, 0x97)
CASCADE_TAG = 0x88
VALID_UID_LENGTHS = (4, 7, 10)
HOST_TIMEOUT_S = 0.2   # the chip's own timer (about 25 ms) normally ends each exchange first


class NoResponse(Exception):
    """The reader chip did not respond (likely wiring, address, power or I2C setup)."""


class InvalidRead(Exception):
    """A malformed, incomplete or colliding card exchange."""


class NoCard(Exception):
    """The chip timer expired: no card answered."""


def crc_a(data):
    """ISO 14443-3 CRC_A, returned low byte first."""
    crc = 0x6363
    for byte in data:
        byte ^= crc & 0xFF
        byte = (byte ^ (byte << 4)) & 0xFF
        crc = ((crc >> 8) ^ (byte << 8) ^ (byte << 3) ^ (byte >> 4)) & 0xFFFF
    return bytes([crc & 0xFF, crc >> 8])


class MFRC522I2C:
    """Minimal MFRC522-compatible client over an smbus2-like bus."""

    def __init__(self, bus, address):
        self._bus, self._address = bus, address

    def _write(self, reg, value):
        self._bus.write_byte_data(self._address, reg, value)

    def _read(self, reg):
        return self._bus.read_byte_data(self._address, reg)

    def _set_bits(self, reg, mask):
        self._write(reg, self._read(reg) | mask)

    def _clear_bits(self, reg, mask):
        self._write(reg, self._read(reg) & ~mask & 0xFF)

    def begin(self):
        """Reset and configure the chip as in the reference MFRC522 driver. Returns version."""
        version = self._read(VERSION)
        if version in (0x00, 0xFF):
            raise NoResponse(f"Implausible chip version 0x{version:02x}")
        self._write(COMMAND, CMD_SOFT_RESET)
        deadline = time.monotonic() + HOST_TIMEOUT_S
        while self._read(COMMAND) & 0x10:                  # PowerDown bit clears after reset
            if time.monotonic() >= deadline:
                raise NoResponse("Chip did not finish soft reset")
            time.sleep(0.005)
        for reg, value in ((TX_MODE, 0x00), (RX_MODE, 0x00), (MOD_WIDTH, 0x26),
                           (T_MODE, 0x80), (T_PRESCALER, 0xA9),        # timer: ~25 ms
                           (T_RELOAD_H, 0x03), (T_RELOAD_L, 0xE8),
                           (TX_ASK, 0x40), (MODE, 0x3D)):
            self._write(reg, value)
        self._set_bits(TX_CONTROL, 0x03)                   # antenna on
        return f"0x{version:02x}"

    def transceive(self, data, tx_last_bits=0):
        """Send bytes to a card and return (response, valid bits in last byte)."""
        self._write(COMMAND, CMD_IDLE)
        self._write(COM_IRQ, 0x7F)                         # clear interrupt flags
        self._write(FIFO_LEVEL, 0x80)                      # flush FIFO
        for byte in data:
            self._write(FIFO_DATA, byte)
        self._write(BIT_FRAMING, tx_last_bits)
        self._write(COMMAND, CMD_TRANSCEIVE)
        self._set_bits(BIT_FRAMING, 0x80)                  # StartSend
        deadline = time.monotonic() + HOST_TIMEOUT_S
        while True:
            irq = self._read(COM_IRQ)
            if irq & (IRQ_RX | IRQ_IDLE):
                break
            if irq & IRQ_TIMER:
                raise NoCard()
            if time.monotonic() >= deadline:
                raise NoResponse("Chip did not complete the card exchange")
        error = self._read(ERROR)
        if error & ERR_PROTOCOL_PARITY_OVERFLOW:
            raise InvalidRead(f"Card exchange error (ErrorReg 0x{error:02x})")
        if error & ERR_COLLISION:
            raise InvalidRead("Collision: more than one card in the field?")
        count = self._read(FIFO_LEVEL) & 0x7F
        response = bytes(self._read(FIFO_DATA) for _ in range(count))
        return response, self._read(CONTROL) & 0x07

    def poll(self):
        """Return (uid, atqa, sak) for one type-A card, or None if no card answered."""
        self._clear_bits(COLL, 0x80)
        try:
            atqa, bits = self.transceive([PICC_WUPA], tx_last_bits=0x07)
        except NoCard:
            return None
        if len(atqa) != 2 or bits:
            raise InvalidRead("Unexpected ATQA")
        uid = b""
        try:
            for level in CASCADE_LEVELS:
                part, _ = self.transceive([level, 0x20])           # anticollision
                if len(part) != 5 or part[0] ^ part[1] ^ part[2] ^ part[3] != part[4]:
                    raise InvalidRead("Bad UID part or check byte")
                frame = bytes([level, 0x70]) + part
                sak_frame, _ = self.transceive(frame + crc_a(frame))  # select
                if len(sak_frame) != 3 or crc_a(sak_frame[:1]) != sak_frame[1:]:
                    raise InvalidRead("Bad SAK response")
                sak = sak_frame[0]
                if sak & 0x04:                                     # UID not complete
                    if part[0] != CASCADE_TAG:
                        raise InvalidRead("Missing cascade tag")
                    uid += part[1:4]
                    continue
                uid += part[:4]
                break
            else:
                raise InvalidRead("UID longer than three cascade levels")
        except NoCard:
            raise InvalidRead("Card read incomplete (card moved away?)") from None
        if len(uid) not in VALID_UID_LENGTHS:
            raise InvalidRead("Invalid UID length")
        halt = bytes([PICC_HLTA, 0x00])
        try:
            self.transceive(halt + crc_a(halt))            # a halted card does not reply
        except NoCard:
            pass
        return uid, atqa, sak


def card_record(uid, atqa, sak, run_key):
    return {
        "present": True,
        "ref": hmac.new(run_key, uid, hashlib.sha256).hexdigest()[:12],
        "uid_bytes": len(uid),
        # ISO 14443-3: a 4-byte UID starting 0x08 is randomly generated per activation.
        "uid_random": len(uid) == 4 and uid[0] == 0x08,
        "atqa": atqa.hex(),
        "sak": f"{sak:02x}",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (Pi header: 1)")
    parser.add_argument("--address", type=lambda v: int(v, 0), default=0x28,
                        help="I2C address (RFID2: 0x28)")
    parser.add_argument("--station-id", default="sensor-test")
    parser.add_argument("--samples", type=int, default=20, help="Number of polls (default: 20)")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between polls (>0)")
    args = parser.parse_args(argv)
    if args.bus < 0:
        parser.error("--bus must not be negative")
    if not 0x08 <= args.address <= 0x77:
        parser.error("--address must be a 7-bit I2C address between 0x08 and 0x77")
    if args.samples < 1:
        parser.error("--samples must be positive")
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be finite and positive")
    if not args.station_id.strip():
        parser.error("--station-id must not be empty")

    bus = None
    try:
        from smbus2 import SMBus

        bus = SMBus(args.bus)
        reader = MFRC522I2C(bus, args.address)
        chip_version = reader.begin()
    except (Exception, SystemExit) as exc:
        print(f"Cannot initialize RFID reader at 0x{args.address:02x} on I2C bus {args.bus}: "
              f"{exc}. Check smbus2 installation, wiring, I2C enabled on the Pi and the "
              "address shown by i2cdetect.", file=sys.stderr)
        if bus is not None:
            bus.close()
        return 1

    run_key = secrets.token_bytes(32)   # never printed; refs are only comparable within a run
    failed = False
    try:
        for attempt in range(args.samples):
            quality, error, card = "experimental", None, None
            started = time.monotonic()
            try:
                result = reader.poll()
                card = {"present": False} if result is None else card_record(*result, run_key)
            except InvalidRead as exc:
                quality, error = "invalid", str(exc)
            except Exception as exc:
                quality, error = "missing", f"RFID read failed: {exc}"
            if error is not None:
                failed = True
            record = {
                "station_id": args.station_id,
                "ts": datetime.now(UTC).isoformat(),
                "model": MODEL,
                "i2c_bus": args.bus,
                "i2c_address": f"0x{args.address:02x}",
                "chip_version": chip_version,
                "card": card,
                "poll_ms": round((time.monotonic() - started) * 1000),
                "quality": quality,
            }
            if error is not None:
                record["error"] = error
            print(json.dumps(record, allow_nan=False), flush=True)
            if attempt + 1 < args.samples:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Sensor test stopped.", file=sys.stderr)
        return 130
    finally:
        bus.close()
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())