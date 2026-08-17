#!/usr/bin/env python3
"""Hardware-independent tests for the Sensel protocol entry points."""

from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest
from unittest.mock import Mock, call


ROOT = Path(__file__).resolve().parent.parent


def load_script(name: str, path: Path):
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise RuntimeError(f"could not create import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


daemon = load_script("sensel_haptic_daemon_for_tests", ROOT / "scripts/sensel-haptic-daemon")
pipe_tool = load_script("sensel_hid_pipe_for_tests", ROOT / "tools/sensel-hid-pipe.py")


class ProtocolEncodingTests(unittest.TestCase):
    def test_read_and_write_commands(self) -> None:
        self.assertEqual(daemon.SenselPipe._command(False, 0x0038, 1), b"\x01\x38\x01")
        self.assertEqual(daemon.SenselPipe._command(True, 0x0038, 1), b"\x81\x38\x01")
        self.assertEqual(
            daemon.SenselPipe._command(True, 0x3FFF, 0xFF), b"\xFF\xFF\xFF"
        )
        self.assertEqual(
            pipe_tool.SenselPipe._command(True, 0x0038, 1), b"\x81\x38\x01"
        )

    def test_command_ranges_are_checked(self) -> None:
        for address in (-1, 0x4000):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    daemon.SenselPipe._command(False, address, 1)

        for size in (-1, 0x100):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    daemon.SenselPipe._command(False, 0, size)


class RegisterOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipe = object.__new__(daemon.SenselPipe)
        self.pipe.write_register = Mock()
        self.pipe.read_register = Mock()

    def test_write_discards_previous_response_bytes(self) -> None:
        self.pipe.rx_buffer = bytearray(b"stale")
        self.pipe._drain = Mock()
        self.pipe._send_payload = Mock()
        self.pipe._receive = Mock(side_effect=[bytes((daemon.WRITE_ACK,)), b"\x00"])

        daemon.SenselPipe.write_register(self.pipe, 0x0038, b"\x01")

        self.assertEqual(self.pipe.rx_buffer, bytearray())
        self.pipe._send_payload.assert_called_once()

    def test_main_click_force_uses_down_and_release_registers(self) -> None:
        self.pipe.read_register.side_effect = [b"R", b"5"]
        self.assertEqual(self.pipe.set_main_click_force(164), (82, 53))
        self.assertEqual(
            self.pipe.write_register.call_args_list,
            [
                call(daemon.CLICK_DOWN_REGISTER, b"R", persist=True),
                call(daemon.CLICK_UP_REGISTER, b"5", persist=True),
            ],
        )

    def test_trackpoint_force_updates_all_six_registers(self) -> None:
        self.pipe.read_register.side_effect = [b"&"] * 3 + [b"\x19"] * 3
        self.assertEqual(self.pipe.set_trackpoint_click_force(38), (38, 25))
        calls = self.pipe.write_register.call_args_list
        self.assertEqual(len(calls), 6)
        self.assertEqual([call.args[1] for call in calls[:3]], [b"&"] * 3)
        self.assertEqual([call.args[1] for call in calls[3:]], [b"\x19"] * 3)
        self.assertTrue(all(call.kwargs["persist"] for call in calls))

    def test_scalar_settings_validate_and_write(self) -> None:
        # No readback for these two: the flash-busy window after a persisted
        # write would stall every adjustment (see daemon comments).
        self.pipe.read_register.side_effect = [b"x"]  # must not be consumed
        self.assertEqual(self.pipe.set_haptic_intensity(100), 100)
        self.assertEqual(
            self.pipe.write_register.call_args,
            call(daemon.HAPTIC_INTENSITY_REGISTER, b"d", persist=True),
        )
        self.pipe.read_register.assert_not_called()

        self.pipe.write_register.reset_mock()
        self.pipe.read_register.reset_mock()
        self.assertEqual(self.pipe.set_trackpoint_buttons(1), 1)
        self.assertEqual(
            self.pipe.write_register.call_args,
            call(daemon.PTP_BUTTONS_CONFIG_REGISTER, b"\x01", persist=True),
        )

    def test_invalid_values_are_rejected(self) -> None:
        invalid_calls = (
            (self.pipe.set_haptic_intensity, (-1,)),
            (self.pipe.set_haptic_intensity, (101,)),
            (self.pipe.set_main_click_force, (121,)),
            (self.pipe.set_main_click_force, (512,)),
            (self.pipe.set_trackpoint_click_force, (0,)),
            (self.pipe.set_trackpoint_click_force, (256,)),
            (self.pipe.set_trackpoint_buttons, (2,)),
        )
        for function, args in invalid_calls:
            with self.subTest(function=function.__name__, args=args):
                with self.assertRaises(ValueError):
                    function(*args)
        self.pipe.write_register.assert_not_called()


class DraftOperationTests(unittest.TestCase):
    """Preview/commit flows backing the GUI draft model (issue #1)."""

    def setUp(self) -> None:
        self.pipe = object.__new__(daemon.SenselPipe)
        self.pipe.write_register = Mock()
        self.pipe.read_register = Mock()

    def test_previews_write_ram_only(self) -> None:
        self.assertEqual(self.pipe.preview_haptic_intensity(77), 77)
        self.pipe.write_register.assert_called_once_with(
            daemon.HAPTIC_INTENSITY_REGISTER, bytes((77,)), persist=False
        )
        self.pipe.write_register.reset_mock()

        self.assertEqual(self.pipe.preview_trackpoint_buttons(1), 1)
        self.pipe.write_register.assert_called_once_with(
            daemon.PTP_BUTTONS_CONFIG_REGISTER, bytes((1,)), persist=False
        )
        self.pipe.write_register.reset_mock()

        self.assertEqual(self.pipe.preview_main_click_force(164), (82, 53))
        self.assertEqual(
            self.pipe.write_register.call_args_list,
            [
                call(daemon.CLICK_DOWN_REGISTER, bytes((82,)), persist=False),
                call(daemon.CLICK_UP_REGISTER, bytes((53,)), persist=False),
            ],
        )
        self.pipe.write_register.reset_mock()

        self.assertEqual(self.pipe.preview_trackpoint_click_force(38), (38, 25))
        for invoked in self.pipe.write_register.call_args_list:
            self.assertIs(invoked.kwargs["persist"], False)
        self.assertEqual(len(self.pipe.write_register.call_args_list), 6)

    def test_previews_do_not_read_back(self) -> None:
        self.pipe.preview_haptic_intensity(50)
        self.pipe.preview_trackpoint_buttons(0)
        self.pipe.preview_main_click_force(120)
        self.pipe.preview_trackpoint_click_force(60)
        self.pipe.read_register.assert_not_called()

    def test_commits_persist_each_register_immediately(self) -> None:
        # Each save reloads the user-setting block from flash, wiping other
        # unsaved RAM values, so a commit must interleave write+save.
        self.assertEqual(self.pipe.commit_main_click_force(190), (95, 62))
        self.assertEqual(
            self.pipe.write_register.call_args_list,
            [
                call(daemon.CLICK_DOWN_REGISTER, bytes((95,)), persist=True),
                call(daemon.CLICK_UP_REGISTER, bytes((62,)), persist=True),
            ],
        )
        self.pipe.read_register.assert_not_called()
        self.pipe.write_register.reset_mock()

        self.assertEqual(self.pipe.commit_trackpoint_click_force(60), (60, 39))
        calls = self.pipe.write_register.call_args_list
        self.assertEqual(len(calls), 6)
        self.assertEqual([c.args[1] for c in calls[:3]], [bytes((60,))] * 3)
        self.assertEqual([c.args[1] for c in calls[3:]], [bytes((39,))] * 3)
        self.assertTrue(all(c.kwargs["persist"] for c in calls))
        self.pipe.read_register.assert_not_called()


if __name__ == "__main__":
    unittest.main()
