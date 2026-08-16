#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read/write the Sensel internal register pipe exposed by hidraw.

The framing is reproduced from SenselSerialDevice.dll 1.5.4.0.  Reading is
safe; writes are intentionally explicit because these are private device
registers.  Run as root (or grant the selected hidraw node to the user).
"""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import select
import stat
import struct
import sys
import time
from pathlib import Path


PIPE_REPORT_ID = 0x09
PIPE_REPORT_SIZE = 21
PIPE_PAYLOAD_SIZE = PIPE_REPORT_SIZE - 2
READ_ACK = 0x01
WRITE_ACK = 0x05
SAVE_REGISTER = 0x0230
USER_SETTING_ATTRIBUTE = 0x4000
REGISTER_LOCK_FILE = "/run/lock/sensel-haptic-touchpad.lock"

REGISTERS = {
    "click-down": 0x0038,
    "click-up": 0x0090,
    "3hb-left-down": 0x0091,
    "3hb-left-up": 0x0092,
    "3hb-right-down": 0x0093,
    "3hb-right-up": 0x0094,
    "3hb-middle-down": 0x0095,
    "3hb-middle-up": 0x0096,
    "trackpoint-buttons": 0x008A,
    "haptic-intensity": 0x00AB,
}

MAIN_CLICK_FORCE_LEVELS = (120, 164, 190)
THREE_HB_CLICK_FORCE_LEVELS = (28, 38, 60)
RELEASE_FORCE_RATIO = 0.65


def parse_int(text: str) -> int:
    try:
        return int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer: {text}") from exc


def validate_device(path: str) -> None:
    if not re.fullmatch(r"/dev/hidraw[0-9]+", path):
        raise ValueError("refusing an unexpected device path")
    if not stat.S_ISCHR(os.stat(path).st_mode):
        raise ValueError("path is not a character device")
    resolved = os.path.realpath(f"/sys/class/hidraw/{Path(path).name}")
    if "SNSL" not in resolved and "2C2F:0028" not in resolved:
        raise ValueError(f"not a Sensel SNSL0028 device: {resolved}")


class SenselPipe:
    def __init__(self, path: str, timeout: float = 2.0) -> None:
        validate_device(path)
        self.lock_file = open(REGISTER_LOCK_FILE, "a+")
        fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except Exception:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            raise
        self.timeout = timeout
        self.rx_buffer = bytearray()

    def close(self) -> None:
        os.close(self.fd)
        fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
        self.lock_file.close()

    def __enter__(self) -> "SenselPipe":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _drain(self) -> None:
        while True:
            ready, _, _ = select.select([self.fd], [], [], 0)
            if not ready:
                return
            try:
                os.read(self.fd, 1024)
            except BlockingIOError:
                return

    def _send_payload(self, payload: bytes) -> None:
        if not payload:
            raise ValueError("empty HID pipe payload")
        for start in range(0, len(payload), PIPE_PAYLOAD_SIZE):
            chunk = payload[start : start + PIPE_PAYLOAD_SIZE]
            report = bytearray(PIPE_REPORT_SIZE)
            report[0] = PIPE_REPORT_ID
            report[1] = len(chunk)
            report[2 : 2 + len(chunk)] = chunk
            written = os.write(self.fd, report)
            if written != PIPE_REPORT_SIZE:
                raise OSError(f"short HID report write: {written}/{PIPE_REPORT_SIZE}")

    def _receive_report_payload(self) -> bytes:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select(
                [self.fd], [], [], max(0.0, deadline - time.monotonic())
            )
            if not ready:
                break
            try:
                report = os.read(self.fd, 1024)
            except BlockingIOError:
                continue
            if len(report) < 2 or report[0] != PIPE_REPORT_ID:
                continue
            count = report[1]
            if count > PIPE_PAYLOAD_SIZE or len(report) < 2 + count:
                continue
            return report[2 : 2 + count]
        raise TimeoutError("timed out waiting for Sensel pipe response")

    def _receive(self, count: int) -> bytes:
        while len(self.rx_buffer) < count:
            self.rx_buffer.extend(self._receive_report_payload())
        result = bytes(self.rx_buffer[:count])
        del self.rx_buffer[:count]
        return result

    @staticmethod
    def _command(is_read: bool, address: int, size: int) -> bytes:
        if not 0 <= address <= 0x3FFF:
            raise ValueError("register address must be between 0 and 0x3fff")
        if not 0 <= size <= 0xFF:
            raise ValueError("register command size must fit in one byte")
        first = ((address & 0x3F00) >> 7) | 0x01
        if is_read:
            first |= 0x80
        return bytes((first, address & 0xFF, size))

    def read_register(self, address: int, size: int) -> bytes:
        if not 1 <= size <= 0xFF:
            raise ValueError("read size must be between 1 and 255")
        self._drain()
        self.rx_buffer.clear()
        self._send_payload(self._command(True, address, size))
        if self._receive(1)[0] != READ_ACK:
            raise RuntimeError("device rejected register read")
        self._receive(1)  # response status, not used by SenselSerialDevice
        reported_size = struct.unpack("<H", self._receive(2))[0]
        if reported_size != size:
            raise RuntimeError(f"read size mismatch: requested {size}, got {reported_size}")
        data = self._receive(size)
        checksum = self._receive(1)[0]
        if (sum(data) & 0xFF) != checksum:
            raise RuntimeError("register read checksum mismatch")
        return data

    def write_register(self, address: int, data: bytes, persist: bool = False) -> None:
        if not 1 <= len(data) <= 0xFF:
            raise ValueError("write size must be between 1 and 255")
        self._drain()
        self.rx_buffer.clear()
        packet = self._command(False, address, len(data))
        packet += data + bytes((sum(data) & 0xFF,))
        self._send_payload(packet)
        if self._receive(1)[0] != WRITE_ACK:
            raise RuntimeError("device rejected register write")
        self._receive(1)  # response status, not used by SenselSerialDevice
        if persist:
            self.save_register(address)

    def save_register(self, address: int) -> None:
        # SenselSerialDevice.SaveRegister(addr, UserSetting) writes a five-byte
        # record to register 0x0230: addr(u16), attribute(u16), operation(0x51).
        record = struct.pack("<HHB", address, USER_SETTING_ATTRIBUTE, 0x51)
        self.write_register(SAVE_REGISTER, record, persist=False)

    def set_main_click_force(self, gf: int, persist: bool = True) -> tuple[int, int]:
        if not 2 <= gf <= 510 or gf % 2:
            raise ValueError("click force must be an even value from 2 to 510 Gf")
        # The main PTP register is stored in Gf/2 units.
        down = gf // 2
        up = int(round(down * RELEASE_FORCE_RATIO))
        self.write_register(REGISTERS["click-down"], bytes((down,)), persist=persist)
        self.write_register(REGISTERS["click-up"], bytes((up,)), persist=persist)
        return down, up

    def set_trackpoint_click_force(
        self, gf: int, persist: bool = True
    ) -> tuple[int, int]:
        if not 1 <= gf <= 255:
            raise ValueError(
                "TrackPoint click force must be a value from 1 to 255 "
                "(Windows TrackPoint register units)"
            )
        # Windows writes the 3HB values directly; do not halve them again.
        down = gf
        up = int(round(down * RELEASE_FORCE_RATIO))
        for name in ("3hb-left-down", "3hb-right-down", "3hb-middle-down"):
            self.write_register(REGISTERS[name], bytes((down,)), persist=persist)
        for name in ("3hb-left-up", "3hb-right-up", "3hb-middle-up"):
            self.write_register(REGISTERS[name], bytes((up,)), persist=persist)
        return down, up


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="/dev/hidraw1")
    parser.add_argument("--timeout", type=float, default=2.0)
    sub = parser.add_subparsers(dest="command", required=True)

    read = sub.add_parser("read", help="read one private register")
    read.add_argument("address", type=parse_int)
    read.add_argument("--size", type=parse_int, default=1)

    write = sub.add_parser("write", help="write raw bytes to one private register")
    write.add_argument("address", type=parse_int)
    write.add_argument("values", nargs="+", type=parse_int)
    write.add_argument("--persist", action="store_true")

    click = sub.add_parser("set-main-click-force", help="set main PTP click force in even Gf")
    click.add_argument("gf", type=parse_int)
    click.add_argument("--no-persist", action="store_true")

    trackpoint = sub.add_parser(
        "set-trackpoint-click-force",
        help="set TrackPoint button click force (Windows register units)",
    )
    trackpoint.add_argument("gf", type=parse_int)
    trackpoint.add_argument("--no-persist", action="store_true")

    buttons = sub.add_parser(
        "set-trackpoint-buttons", help="enable or disable TrackPoint buttons"
    )
    buttons.add_argument("enabled", type=parse_int, choices=(0, 1))
    buttons.add_argument("--no-persist", action="store_true")

    intensity = sub.add_parser("set-haptic-intensity", help="set haptic feedback intensity")
    intensity.add_argument("value", type=parse_int)
    intensity.add_argument("--no-persist", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with SenselPipe(args.device, args.timeout) as pipe:
            if args.command == "read":
                data = pipe.read_register(args.address, args.size)
                print(f"0x{args.address:04x}: {data.hex(' ')} ({int.from_bytes(data, 'little')})")
            elif args.command == "write":
                if any(not 0 <= value <= 0xFF for value in args.values):
                    raise ValueError("raw register values must be between 0 and 255")
                pipe.write_register(
                    args.address, bytes(args.values), persist=args.persist
                )
                print(f"wrote 0x{args.address:04x}: {' '.join(f'{x:02x}' for x in args.values)}")
            elif args.command == "set-main-click-force":
                down, up = pipe.set_main_click_force(args.gf, persist=not args.no_persist)
                print(f"click-down=0x{down:02x}, click-up=0x{up:02x}")
            elif args.command == "set-trackpoint-click-force":
                down, up = pipe.set_trackpoint_click_force(
                    args.gf, persist=not args.no_persist
                )
                print(
                    f"trackpoint-click-down=0x{down:02x}, "
                    f"trackpoint-click-up=0x{up:02x}"
                )
            elif args.command == "set-trackpoint-buttons":
                pipe.write_register(
                    REGISTERS["trackpoint-buttons"],
                    bytes((args.enabled,)),
                    persist=not args.no_persist,
                )
                print(f"trackpoint-buttons={args.enabled}")
            elif args.command == "set-haptic-intensity":
                if not 0 <= args.value <= 100:
                    raise ValueError("haptic intensity must be between 0 and 100")
                pipe.write_register(
                    REGISTERS["haptic-intensity"],
                    bytes((args.value,)),
                    persist=not args.no_persist,
                )
                print(f"haptic-intensity={args.value}")
            return 0
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        print(f"sensel-hid-pipe: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
