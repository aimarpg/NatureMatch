"""Software-only checks for read_nfc.py using a simulated MFRC522-compatible chip and card.

No RFID hardware is involved; these tests do not validate the physical M5Stack Unit RFID2.
"""
import contextlib
import importlib.util
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = (Path(__file__).resolve().parents[2]
          / "src/naturematch/tools/hardware/read_nfc.py")
spec = importlib.util.spec_from_file_location("read_nfc", SCRIPT)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)

UID4 = bytes.fromhex("1a2b3c4d")              # simulated identifiers only
UID7 = bytes.fromhex("04a1b2c3d4e5f6")
UID10 = bytes.fromhex("0411223344556677889a")
UID_RANDOM = bytes.fromhex("08112233")


class SimulatedCard:
    """ISO 14443-A card answering WUPA, anticollision, select and HLTA.
    `schedule` gives one entry per poll: a UID, None (no card) or a fault name."""

    def __init__(self, schedule):
        self.schedule = list(schedule)
        self.uid = None
        self.fault = None
        self.error = 0

    def parts(self):
        u = self.uid
        if len(u) == 4:
            return [u]
        if len(u) == 7:
            return [bytes([0x88]) + u[:3], u[3:]]
        return [bytes([0x88]) + u[:3], bytes([0x88]) + u[3:6], u[6:]]

    def handle(self, frame, bits):
        self.error = 0
        if bits == 7 and frame == bytes([r.PICC_WUPA]):
            entry = self.schedule.pop(0) if self.schedule else None
            self.uid, self.fault = (entry, None) if not isinstance(entry, str) else (UID7, entry)
            if self.uid is None:
                return None
            return b"\x04\x00" if len(self.uid) == 4 else b"\x44\x00"
        if self.uid is None or self.fault == "vanish":
            return None
        if frame[:2] == bytes([r.PICC_HLTA, 0x00]):
            assert r.crc_a(frame[:2]) == frame[2:], "reader sent bad CRC"
            return None                                         # halted cards stay silent
        level = r.CASCADE_LEVELS.index(frame[0])
        part = self.parts()[level]
        if frame[1:2] == b"\x20":                               # anticollision
            if self.fault == "collision":
                self.error = r.ERR_COLLISION
            bcc = part[0] ^ part[1] ^ part[2] ^ part[3]
            return part + bytes([bcc ^ (0xFF if self.fault == "bad_bcc" else 0)])
        if frame[1:2] == b"\x70":                               # select
            assert r.crc_a(frame[:-2]) == frame[-2:], "reader sent bad CRC"
            sak = bytes([0x04 if level + 1 < len(self.parts()) else 0x00])
            return sak + r.crc_a(sak)
        raise AssertionError(f"unexpected frame {frame.hex()}")


class SimulatedMFRC522Bus:
    """smbus2-like bus exposing an MFRC522-compatible register set at 0x28."""

    def __init__(self, card, version=0x92, address=0x28, dead_after_polls=None):
        self.card, self.version, self.address = card, version, address
        self.regs, self.fifo = {}, []
        self.dead_after_polls = dead_after_polls
        self.polls = 0
        self.closed = False
        self.antenna_on = False

    def _check(self, addr):
        if addr != self.address:
            raise OSError(121, "Remote I/O error")
        if self.dead_after_polls is not None and self.polls > self.dead_after_polls:
            raise OSError(121, "Remote I/O error")

    def write_byte_data(self, addr, reg, value):
        self._check(addr)
        if reg == r.FIFO_DATA:
            self.fifo.append(value)
        elif reg == r.FIFO_LEVEL and value & 0x80:
            self.fifo.clear()
        elif reg == r.COM_IRQ:
            self.regs[reg] = self.regs.get(reg, 0) & ~value
        elif reg == r.COMMAND and value == r.CMD_SOFT_RESET:
            self.regs = {}
        elif reg == r.BIT_FRAMING:
            self.regs[reg] = value
            if value & 0x80 and self.regs.get(r.COMMAND) == r.CMD_TRANSCEIVE:
                frame, self.fifo = bytes(self.fifo), []
                if frame == bytes([r.PICC_WUPA]):
                    self.polls += 1
                response = self.card.handle(frame, value & 0x07)
                self.regs[r.ERROR] = self.card.error
                if response is None:
                    self.regs[r.COM_IRQ] = r.IRQ_TIMER
                else:
                    self.fifo = list(response)
                    self.regs[r.COM_IRQ] = r.IRQ_RX | r.IRQ_IDLE
        else:
            self.regs[reg] = value
            if reg == r.TX_CONTROL:
                self.antenna_on = value & 0x03 == 0x03

    def read_byte_data(self, addr, reg):
        self._check(addr)
        if reg == r.VERSION:
            return self.version
        if reg == r.FIFO_DATA:
            return self.fifo.pop(0)
        if reg == r.FIFO_LEVEL:
            return len(self.fifo)
        return self.regs.get(reg, 0)

    def close(self):
        self.closed = True


class SimulatedType4Phone(SimulatedCard):
    """Type 4 text tag with the same simulated UID across taps."""

    def __init__(self, *messages):
        super().__init__([UID_RANDOM] * len(messages))
        self.messages = iter(messages)

    def handle(self, frame, bits):
        if bits == 7 and frame == b"\x52":
            reply = super().handle(frame, bits)
            if reply is not None:
                message = next(self.messages)
                record = b""
                if message is not None:
                    text = message.encode("utf-8")
                    record = bytes([0xD1, 1, len(text) + 3]) + b"T\x02en" + text
                self.ndef = len(record).to_bytes(2, "big") + record
            return reply
        if frame[0] in r.CASCADE_LEVELS:
            reply = super().handle(frame, bits)
            return b"\x20" + r.crc_a(b"\x20") if frame[1] == 0x70 else reply
        if frame[:2] == b"\x50\x00":
            return super().handle(frame, bits)
        assert bits == 0 and r.crc_a(frame[:-2]) == frame[-2:]
        request = frame[:-2]
        if request == b"\xe0\x50":
            self.block = 0
            self.file = None
            reply = b"\x02\x05"
        elif request == b"\xc2":
            reply = request
        elif request == b"\xf2\x02":
            reply = self.pending_reply
        else:
            pcb, command = request[0], request[1:]
            assert pcb == 0x02 | self.block
            self.block ^= 1
            data = b""
            if command == bytes.fromhex("00a4040007d276000085010100"):
                self.pending_reply = bytes([pcb]) + b"\x90\x00"
                reply = b"\xf2\x02"
                return reply + r.crc_a(reply)
            elif command == bytes.fromhex("00a4000c02e103"):
                self.file = bytes.fromhex("000f20001000340406e10400ff00ff")
            elif command == bytes.fromhex("00a4000c02e104"):
                self.file = self.ndef
            else:
                assert command[:2] == b"\x00\xb0" and self.file is not None
                offset = int.from_bytes(command[2:4], "big")
                count = command[4]
                assert count <= 16
                data = self.file[offset:offset + count]
            reply = bytes([pcb]) + data + b"\x90\x00"
        return reply + r.crc_a(reply)


class ReadNfcToolTest(unittest.TestCase):
    def run_tool(self, bus, *extra):
        fake = types.SimpleNamespace(SMBus=mock.Mock(return_value=bus))
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(sys.modules, {"smbus2": fake}), \
                mock.patch.object(r.time, "sleep"), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = r.main(["--interval", "0.01", *extra])
        records = [json.loads(line) for line in out.getvalue().splitlines()]
        return code, records, out.getvalue() + err.getvalue()

    def test_crc_a_known_values(self):
        self.assertEqual(r.crc_a(b"\x00\x00"), bytes.fromhex("a01e"))
        self.assertEqual(r.crc_a(b"\x50\x00"), bytes.fromhex("57cd"))   # HLTA

    def test_type4_phone_reports_changed_text(self):
        phone = SimulatedType4Phone("activity=study", "activity=socialise")
        code, records, _ = self.run_tool(SimulatedMFRC522Bus(phone), "--samples", "3")
        self.assertEqual(code, 0)
        self.assertEqual([record["card"].get("payload") for record in records],
                         ["activity=study", "activity=socialise", None])
        self.assertEqual(records[2]["card"], {"present": False})

    def test_type4_phone_reports_empty_ndef_and_recovers(self):
        phone = SimulatedType4Phone("activity=study", None, "activity=socialise")
        bus = SimulatedMFRC522Bus(phone)
        code, records, _ = self.run_tool(bus, "--samples", "3")
        self.assertEqual(code, 1)
        self.assertTrue(records[1]["card"]["present"])
        self.assertIsNone(records[1]["card"]["payload"])
        self.assertEqual(records[1]["quality"], "invalid")
        self.assertIn("no NDEF message", records[1]["error"])
        self.assertEqual(records[2]["card"]["payload"], "activity=socialise")
        self.assertTrue(bus.antenna_on)

    def test_help_needs_no_smbus(self):
        with mock.patch.dict(sys.modules, {"smbus2": None}), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            r.main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_uid_lengths_read_without_printing_raw_uid(self):
        for uid in (UID4, UID7, UID10):
            with self.subTest(uid_bytes=len(uid)):
                bus = SimulatedMFRC522Bus(SimulatedCard([uid, uid]))
                code, records, text = self.run_tool(bus, "--samples", "2")
                self.assertEqual(code, 0)
                self.assertNotIn(uid.hex(), text.lower())
                card = records[0]["card"]
                self.assertTrue(card["present"])
                self.assertEqual(card["uid_bytes"], len(uid))
                self.assertEqual(len(card["ref"]), 12)
                self.assertEqual(card["ref"], records[1]["card"]["ref"])
                self.assertEqual(card["sak"], "00")
                self.assertTrue(bus.antenna_on)
                self.assertTrue(bus.closed)

    def test_record_fields(self):
        _, records, _ = self.run_tool(SimulatedMFRC522Bus(SimulatedCard([UID4])),
                                      "--samples", "1", "--station-id", "NM-01")
        rec = records[0]
        self.assertEqual(rec["station_id"], "NM-01")
        self.assertEqual(rec["i2c_address"], "0x28")
        self.assertEqual(rec["chip_version"], "0x92")
        self.assertEqual(rec["quality"], "experimental")
        for key in ("ts", "model", "i2c_bus", "poll_ms"):
            self.assertIn(key, rec)

    def test_refs_not_linkable_across_runs(self):
        _, a, _ = self.run_tool(SimulatedMFRC522Bus(SimulatedCard([UID7])), "--samples", "1")
        _, b, _ = self.run_tool(SimulatedMFRC522Bus(SimulatedCard([UID7])), "--samples", "1")
        self.assertNotEqual(a[0]["card"]["ref"], b[0]["card"]["ref"])

    def test_no_card_is_valid(self):
        code, records, _ = self.run_tool(SimulatedMFRC522Bus(SimulatedCard([None])),
                                         "--samples", "1")
        self.assertEqual(code, 0)
        self.assertEqual(records[0]["card"], {"present": False})
        self.assertEqual(records[0]["quality"], "experimental")

    def test_random_uid_flagged(self):
        _, records, text = self.run_tool(SimulatedMFRC522Bus(SimulatedCard([UID_RANDOM])),
                                         "--samples", "1")
        self.assertTrue(records[0]["card"]["uid_random"])
        self.assertNotIn(UID_RANDOM.hex(), text.lower())

    def test_faults_are_invalid_and_not_reused(self):
        for fault in ("bad_bcc", "collision", "vanish"):
            with self.subTest(fault=fault):
                bus = SimulatedMFRC522Bus(SimulatedCard([UID7, fault]))
                code, records, _ = self.run_tool(bus, "--samples", "2")
                self.assertEqual(code, 1)
                self.assertTrue(records[0]["card"]["present"])
                self.assertIsNone(records[1]["card"])
                self.assertEqual(records[1]["quality"], "invalid")
                self.assertIn("error", records[1])

    def test_wrong_address_fails_initialization(self):
        bus = SimulatedMFRC522Bus(SimulatedCard([]), address=0x29)
        code, records, text = self.run_tool(bus)
        self.assertEqual(code, 1)
        self.assertEqual(records, [])
        self.assertIn("Cannot initialize RFID reader", text)
        self.assertTrue(bus.closed)

    def test_implausible_version_fails_initialization(self):
        for version in (0x00, 0xFF):
            with self.subTest(version=version):
                code, records, _ = self.run_tool(
                    SimulatedMFRC522Bus(SimulatedCard([]), version=version))
                self.assertEqual(code, 1)
                self.assertEqual(records, [])

    def test_bus_failure_mid_run_is_missing(self):
        bus = SimulatedMFRC522Bus(SimulatedCard([UID4, UID4]), dead_after_polls=1)
        code, records, _ = self.run_tool(bus, "--samples", "2")
        self.assertEqual(code, 1)
        self.assertEqual(records[0]["quality"], "experimental")
        self.assertEqual(records[1]["quality"], "missing")
        self.assertIsNone(records[1]["card"])

    def test_keyboard_interrupt(self):
        bus = SimulatedMFRC522Bus(SimulatedCard([UID4]))
        with mock.patch.object(r.MFRC522I2C, "poll", side_effect=KeyboardInterrupt):
            code, _, _ = self.run_tool(bus)
        self.assertEqual(code, 130)
        self.assertTrue(bus.closed)

    def test_argument_errors(self):
        for argv in (["--samples", "0"], ["--interval", "nan"], ["--interval", "0"],
                     ["--address", "0x80"], ["--address", "zz"], ["--bus", "-1"],
                     ["--station-id", " "]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit) as cm:
                r.main(argv)
            self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
