"""Test an M5Stack Unit RFID2 (WS1850S, MFRC522-compatible) reader over I2C.

Polls for ISO 14443-A cards/tags and prints one JSON line per attempt. Raw card
identifiers are never printed: each UID is replaced by an HMAC reference keyed
with a random per-run secret, so repeat taps can be recognised within one run but
not linked across runs. For Type 4 tags, reads a single NDEF Text record and
prints it as card.payload. Use synthetic text for this standalone diagnostic.
It creates no check-in sessions or station observations.
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
ISO_DEP_TIMEOUT_S = 0.5
NDEF_APP_SELECT = bytes.fromhex("00 A4 04 00 07 D2 76 00 00 85 01 01 00")
MAX_NDEF_BYTES = 1024


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


def ndef_text(message):
    """Decode the single well-known Text record produced by the emulator."""
    if not message:
        raise InvalidRead("The Type 4 tag contains no NDEF message")
    header = message[0]
    if header & 0xEF != 0xC1:
        raise InvalidRead("Expected a single NDEF Text record")
    type_offset = 3 if header & 0x10 else 6
    length = int.from_bytes(message[2:type_offset], "big")
    payload = message[type_offset + 1:]
    if message[1:2] != b"\x01" or message[type_offset:type_offset + 1] != b"T":
        raise InvalidRead("Expected an NDEF Text record")
    if not payload or len(payload) != length:
        raise InvalidRead("Invalid NDEF Text record length")
    status = payload[0]
    text_offset = 1 + (status & 0x3F)
    if status & 0x40 or text_offset > len(payload):
        raise InvalidRead("Invalid NDEF Text language field")
    encoding = "utf-8"
    if status & 0x80:
        bom = payload[text_offset:text_offset + 2]
        encoding = "utf-16" if bom in (b"\xff\xfe", b"\xfe\xff") else "utf-16-be"
    try:
        return payload[text_offset:].decode(encoding)
    except UnicodeError:
        raise InvalidRead("Invalid NDEF Text encoding") from None


class Type4TextReader:
    """Read a small Type 4 NDEF message over ISO-DEP with no CID or NAD."""

    def __init__(self, transceive):
        self.transceive = transceive
        self.block = 0

    def exchange(self, frame):
        reply, bits = self.transceive(frame + crc_a(frame), timeout=ISO_DEP_TIMEOUT_S)
        if bits or len(reply) < 3 or crc_a(reply[:-2]) != reply[-2:]:
            raise InvalidRead("Invalid ISO-DEP frame or CRC")
        return reply[:-2]

    def command(self, apdu):
        pcb = self.block | 0x02
        reply = self.exchange(bytes([pcb]) + apdu)
        # Android may ask for more processing time before replying to an APDU.
        for _ in range(4):
            if reply[0] != 0xF2:
                break
            if len(reply) != 2 or not 1 <= (reply[1] & 0x3F) <= 59:
                raise InvalidRead("Invalid ISO-DEP waiting-time request")
            reply = self.exchange(bytes([0xF2, reply[1] & 0x3F]))
        if reply[0] != pcb or len(reply) < 3:
            raise InvalidRead("Unexpected ISO-DEP response block")
        self.block ^= 1
        if reply[-2:] != b"\x90\x00":
            raise InvalidRead(f"Type 4 command rejected (status {reply[-2:].hex()})")
        return reply[1:-2]

    def select_file(self, file_id):
        self.command(b"\x00\xa4\x00\x0c\x02" + file_id)

    def read_binary(self, offset, length):
        data = self.command(b"\x00\xb0" + offset.to_bytes(2, "big") + bytes([length]))
        if len(data) != length:
            raise InvalidRead("Incomplete Type 4 file read")
        return data

    def read_text(self):
        # FSDI=5 requests frames up to 64 bytes, the size of the reader's FIFO.
        ats = self.exchange(b"\xe0\x50")
        if ats[0] != len(ats):
            raise InvalidRead("Invalid ISO-DEP activation response")

        self.command(NDEF_APP_SELECT)
        self.select_file(b"\xe1\x03")
        container = self.read_binary(0, 15)
        read_limit = min(int.from_bytes(container[3:5], "big"), 48)
        # The initial NDEF File Control TLV supplies the file ID, size and access.
        if (int.from_bytes(container[:2], "big") < 15 or container[7:9] != b"\x04\x06"
                or container[13] != 0 or read_limit < 2):
            raise InvalidRead("Unsupported Type 4 capability container")

        self.select_file(container[9:11])
        size = int.from_bytes(self.read_binary(0, 2), "big")
        file_size = int.from_bytes(container[11:13], "big")
        if size > min(file_size - 2, MAX_NDEF_BYTES):
            raise InvalidRead("NDEF message exceeds the readable file or diagnostic limit")

        message = bytearray()
        while len(message) < size:
            offset = len(message)
            message.extend(self.read_binary(2 + offset, min(size - offset, read_limit)))
        return ndef_text(bytes(message))


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

    def transceive(self, data, tx_last_bits=0, timeout=HOST_TIMEOUT_S):
        """Send bytes to a card and return (response, valid bits in last byte)."""
        self._write(COMMAND, CMD_IDLE)
        self._write(COM_IRQ, 0x7F)                         # clear interrupt flags
        self._write(FIFO_LEVEL, 0x80)                      # flush FIFO
        for byte in data:
            self._write(FIFO_DATA, byte)
        self._write(BIT_FRAMING, tx_last_bits)
        self._write(COMMAND, CMD_TRANSCEIVE)
        self._set_bits(BIT_FRAMING, 0x80)                  # StartSend
        deadline = time.monotonic() + timeout
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
        """Return card details and optional Type 4 text, or None if no card answered."""
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
        if sak & 0x20:
            payload, error = self.read_type4()
            return uid, atqa, sak, payload, error

        halt = bytes([PICC_HLTA, 0x00])
        try:
            self.transceive(halt + crc_a(halt))            # a halted card does not reply
        except NoCard:
            pass
        return uid, atqa, sak, None, None

    def read_type4(self):
        reader = Type4TextReader(self.transceive)
        payload = None
        # HCE replies can take longer than the ~25 ms used for basic discovery.
        self._write(T_RELOAD_H, 0x3E)
        self._write(T_RELOAD_L, 0x80)
        try:
            payload = reader.read_text()
            if reader.exchange(b"\xc2") != b"\xc2":
                raise InvalidRead("Invalid ISO-DEP deselect response")
            return payload, None
        except (InvalidRead, NoCard) as exc:
            # Dropping the field resets a phone left midway through a session.
            self._clear_bits(TX_CONTROL, 0x03)
            time.sleep(0.01)
            self._set_bits(TX_CONTROL, 0x03)
            if payload is not None:
                return payload, None
            return None, str(exc) or "Type 4 tag stopped responding"
        finally:
            self._write(T_RELOAD_H, 0x03)
            self._write(T_RELOAD_L, 0xE8)


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
                if result is None:
                    card = {"present": False}
                else:
                    uid, atqa, sak, payload, payload_error = result
                    card = card_record(uid, atqa, sak, run_key)
                    if sak & 0x20:
                        card["payload"] = payload
                    if payload_error is not None:
                        quality, error = "invalid", payload_error
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
