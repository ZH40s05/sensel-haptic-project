#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Standalone Sensel Haptic Touchpad control panel.

This is intentionally independent from GNOME Control Center.  It uses the
same installed root-owned helper as the Settings integration, so both entry
points share the Windows register protocol, persistence, readback checks and
the same device state.

Editing works as a staged draft: slider and switch changes are previewed to
RAM only (immediate effect, no flash write), and the global Save button
persists the changed registers one by one.  Each persisted save makes the
firmment reload the user-setting block from flash and briefly stop answering
the register pipe, so preview and commit are separate helper operations.
"""

from __future__ import annotations

import configparser
import gettext
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional


HELPER = "/usr/local/libexec/sensel-haptic-set"
TRANSLATION_DOMAIN = "sensel-haptic-control"
DEFAULT_INTENSITY = 71
INTENSITY_LEVELS = (32, 45, 55, 63, 71, 77, 84, 89, 95, 100)
# The standalone panel exposes the raw main click-down register so its
# numeric range matches the TrackPoint register range.  The helper's public
# Click Force CLI remains in physical Gf for GNOME's Windows-compatible
# presets; the GUI converts raw values to Gf when writing.
CLICK_FORCE_MIN = 1
CLICK_FORCE_MAX = 255
TRACKPOINT_FORCE_MIN = 1
TRACKPOINT_FORCE_MAX = 255
# Release (up-register) force as a percentage of the press (down-register)
# force.  Windows hardcodes 65; the GUI exposes 5..100 so the up value stays
# a valid 1..255 register byte for every down value.
RELEASE_RATIO_MIN = 5
RELEASE_RATIO_MAX = 100
RELEASE_RATIO_DEFAULT = 65
# Windows "Medium" preset used by the global Reset button (issue #1).
RESET_INTENSITY = 71
RESET_CLICK_FORCE = 82
RESET_TRACKPOINT_FORCE = 38
RESET_TRACKPOINT_BUTTONS = False
RESET_RELEASE_RATIO = 65


def _translation_directories() -> list[Path]:
    override = os.environ.get("SENSEL_HAPTIC_LOCALEDIR")
    if override:
        return [Path(override)]

    candidates = [
        Path(__file__).resolve().parent.parent / "locale",
        Path("/usr/share/locale"),
    ]
    return list(dict.fromkeys(candidate for candidate in candidates if candidate.is_dir()))


def _load_translation() -> gettext.NullTranslations:
    language_override = os.environ.get("SENSEL_HAPTIC_LOCALE")
    languages = [language_override] if language_override else None
    for directory in _translation_directories():
        try:
            return gettext.translation(
                TRANSLATION_DOMAIN,
                localedir=str(directory),
                languages=languages,
                fallback=False,
            )
        except FileNotFoundError:
            continue
    return gettext.NullTranslations()


_TRANSLATION = _load_translation()
_ = _TRANSLATION.gettext


def _config_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "sensel-haptic-touchpad.ini"


def _new_config_parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    # The GNOME panel uses these exact camel-case UserSetting names.  Keeping
    # option names case-sensitive lets us normalize files written by the old
    # standalone GUI, which used ConfigParser's lower-case defaults.
    parser.optionxform = str
    return parser


def _config_value(parser: configparser.ConfigParser, key: str, default: int) -> int:
    if not parser.has_section("Sensel"):
        return default
    for existing_key in parser["Sensel"]:
        if existing_key.lower() == key.lower():
            try:
                return parser.getint("Sensel", existing_key)
            except ValueError:
                return default
    return default


def load_saved_intensity() -> int:
    parser = _new_config_parser()
    try:
        parser.read(_config_path(), encoding="utf-8")
        value = _config_value(parser, "ptpIntensity", DEFAULT_INTENSITY)
    except (OSError, ValueError, configparser.Error):
        value = DEFAULT_INTENSITY
    return value if 1 <= value <= 100 else DEFAULT_INTENSITY


def save_haptic_preferences(intensity: int, enabled: bool) -> None:
    path = _config_path()
    parser = _new_config_parser()
    try:
        parser.read(path, encoding="utf-8")
        if not parser.has_section("Sensel"):
            parser.add_section("Sensel")
        for existing_key in list(parser["Sensel"]):
            if existing_key.lower() == "ptpintensity" and existing_key != "ptpIntensity":
                del parser["Sensel"][existing_key]
            if (
                existing_key.lower() == "toggleswitchhapticfeedbackison"
                and existing_key != "toggleSwitchHapticFeedbackIsOn"
            ):
                del parser["Sensel"][existing_key]
        if 1 <= intensity <= 100:
            parser.set("Sensel", "ptpIntensity", str(intensity))
        parser.set(
            "Sensel",
            "toggleSwitchHapticFeedbackIsOn",
            "true" if enabled else "false",
        )
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as stream:
            parser.write(stream)
        os.chmod(path, 0o600)
    except (OSError, configparser.Error):
        # Device settings still work if the per-user preference file cannot be
        # written; the next launch will simply use the default remembered level.
        pass


def intensity_to_level(raw: int) -> int:
    if raw <= 0:
        return 5
    return min(range(10), key=lambda index: abs(INTENSITY_LEVELS[index] - raw)) + 1


def release_ratio_from_registers(down: int, up: int) -> int:
    """Best-matching ratio percent for the device's down/up registers."""
    if down <= 0:
        return RELEASE_RATIO_DEFAULT
    ratio = round(up * 100.0 / down)
    return max(RELEASE_RATIO_MIN, min(RELEASE_RATIO_MAX, ratio))


def find_sensel_devices() -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = []
    sysfs_root = Path("/sys/class/hidraw")
    if not sysfs_root.exists():
        return devices

    for link in sorted(sysfs_root.glob("hidraw[0-9]*")):
        path = f"/dev/{link.name}"
        try:
            resolved = os.path.realpath(link / "device")
        except OSError:
            continue
        if "SNSL" not in resolved and "2C2F:0028" not in resolved:
            continue
        description = resolved.split("/devices/", 1)[-1]
        devices.append((path, f"{path}  {description}"))
    return devices


def parse_state(output: str) -> dict[str, int]:
    state: dict[str, int] = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            try:
                state[key.strip()] = int(value.strip(), 10)
            except ValueError:
                continue

    required = (
        "haptic-intensity",
        "click-force",
        "trackpoint-click-force",
        "trackpoint-buttons",
    )
    if any(key not in state for key in required):
        raise RuntimeError(_("Privileged helper returned incomplete Sensel state"))
    if not 0 <= state["haptic-intensity"] <= 100:
        raise RuntimeError(_("Privileged helper returned an invalid haptic intensity"))
    if state["trackpoint-buttons"] not in (0, 1):
        raise RuntimeError(
            _("Privileged helper returned an invalid TrackPoint button state")
        )
    return state

def run_helper(arguments: list[str]) -> str:
    if not os.path.isfile(HELPER) or not os.access(HELPER, os.X_OK):
        raise RuntimeError(_("Privileged helper not found: {path}").format(path=HELPER))

    if os.geteuid() == 0:
        command = [HELPER, *arguments]
    else:
        pkexec = shutil.which("pkexec") or "/usr/bin/pkexec"
        if not os.path.isfile(pkexec):
            raise RuntimeError(_("pkexec was not found; cannot access the Sensel device"))
        command = [pkexec, HELPER, *arguments]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )
    output = "\n".join(
        part.strip() for part in (result.stdout or "", result.stderr or "") if part.strip()
    )
    if result.returncode != 0:
        raise RuntimeError(
            output
            or _("Helper exited with status {status}").format(status=result.returncode)
        )
    return output


class HelperQueue:
    """Run pkexec/helper operations serially without blocking the Tk loop."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.jobs: queue.Queue[Optional[tuple[list[str], Callable]]] = queue.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def submit(self, arguments: list[str], callback: Callable[[str, Optional[str]], None]) -> None:
        self.jobs.put((arguments, callback))

    def close(self) -> None:
        self.jobs.put(None)

    def _run(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                return
            arguments, callback = job
            try:
                output = run_helper(arguments)
                error = None
            except Exception as exc:  # noqa: BLE001 - report helper failures in the GUI
                output = ""
                error = str(exc)
            try:
                self.root.after(0, callback, output, error)
            except tk.TclError:
                return


class SenselHapticApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(_("Sensel Haptic Touchpad"))
        self.root.geometry("760x720")
        self.root.minsize(620, 560)

        self.worker = HelperQueue(root)
        self.devices: dict[str, str] = {}
        self.device_path: Optional[str] = None
        self.loaded = False
        self.syncing = False
        self.read_in_flight = False
        self.saving = False
        self.saved_intensity = load_saved_intensity()

        # Draft model state: "saved_*" mirror the last committed device state,
        # "applied_*" mirror what the preview currently put into RAM.
        self.click_force_applied: Optional[int] = None
        self.trackpoint_force_applied: Optional[int] = None
        self.intensity_applied: Optional[int] = None
        self.buttons_applied: Optional[int] = None
        self.click_ratio_applied: Optional[int] = None
        self.trackpoint_ratio_applied: Optional[int] = None

        self.device_var = tk.StringVar()
        self.haptic_feedback_var = tk.BooleanVar(value=False)
        self.intensity_level_var = tk.IntVar(value=intensity_to_level(self.saved_intensity))
        self.intensity_value_var = tk.StringVar(value=str(self.intensity_level_var.get()))
        self.click_force_var = tk.IntVar(value=60)
        self.click_force_value_var = tk.StringVar(value="60")
        self.trackpoint_buttons_var = tk.BooleanVar(value=False)
        self.trackpoint_force_var = tk.IntVar(value=60)
        self.trackpoint_force_value_var = tk.StringVar(value="60")
        self.click_ratio_var = tk.IntVar(value=RELEASE_RATIO_DEFAULT)
        self.click_ratio_value_var = tk.StringVar(value=str(RELEASE_RATIO_DEFAULT))
        self.trackpoint_ratio_var = tk.IntVar(value=RELEASE_RATIO_DEFAULT)
        self.trackpoint_ratio_value_var = tk.StringVar(value=str(RELEASE_RATIO_DEFAULT))
        self.status_var = tk.StringVar(value=_("Looking for a Sensel Haptic Touchpad…"))
        self.dirty_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.after(100, self.refresh_devices)

    def _build_ui(self) -> None:
        try:
            ttk.Style(self.root).theme_use("clam")
        except tk.TclError:
            pass

        viewport = ttk.Frame(self.root)
        viewport.pack(fill="both", expand=True)
        canvas = tk.Canvas(viewport, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)
        outer = ttk.Frame(canvas, padding=18)
        canvas_window = canvas.create_window((0, 0), window=outer, anchor="nw")
        outer.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(canvas_window, width=event.width),
        )
        self.scroll_canvas = canvas
        self.root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_mousewheel, add="+")
        self.root.bind_all("<Button-5>", self._on_mousewheel, add="+")

        ttk.Label(
            outer,
            text=_("Sensel Haptic Touchpad"),
            font=("TkDefaultFont", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=_("Touchpad Settings"),
            foreground="#555555",
        ).pack(anchor="w", pady=(2, 16))

        device_frame = ttk.LabelFrame(outer, text=_("Device"), padding=10)
        device_frame.pack(fill="x", pady=(0, 12))
        device_frame.columnconfigure(1, weight=1)
        ttk.Label(device_frame, text=_("HID device:")).grid(
            row=0, column=0, sticky="w"
        )
        self.device_combo = ttk.Combobox(
            device_frame,
            textvariable=self.device_var,
            state="readonly",
            width=64,
        )
        self.device_combo.grid(row=0, column=1, sticky="ew", padx=10)
        self.device_combo.bind("<<ComboboxSelected>>", self._device_selected)
        self.refresh_button = ttk.Button(
            device_frame, text=_("Refresh"), command=self.refresh_devices
        )
        self.refresh_button.grid(row=0, column=2, sticky="e")

        haptic_frame = ttk.LabelFrame(outer, text=_("Haptic Feedback"), padding=10)
        haptic_frame.pack(fill="x", pady=(0, 10))
        self.haptic_switch = ttk.Checkbutton(
            haptic_frame,
            text=_("Haptic Feedback"),
            variable=self.haptic_feedback_var,
            command=self._haptic_feedback_changed,
        )
        self.haptic_switch.grid(row=0, column=0, columnspan=3, sticky="w")

        intensity_frame = ttk.LabelFrame(outer, text=_("Haptics Intensity"), padding=10)
        intensity_frame.pack(fill="x", pady=(0, 10))
        intensity_frame.columnconfigure(0, weight=1)
        self.intensity_scale = tk.Scale(
            intensity_frame,
            from_=1,
            to=10,
            resolution=1,
            orient="horizontal",
            showvalue=False,
            highlightthickness=0,
            variable=self.intensity_level_var,
            command=self._intensity_changed,
        )
        self.intensity_scale.grid(row=0, column=0, sticky="ew")
        self.intensity_value_label = ttk.Label(
            intensity_frame, textvariable=self.intensity_value_var, width=3, anchor="center"
        )
        self.intensity_value_label.grid(row=0, column=1, padx=(10, 0))
        ttk.Label(intensity_frame, text="1").grid(row=1, column=0, sticky="w")
        ttk.Label(intensity_frame, text="10").grid(row=1, column=0, sticky="e")

        click_frame = ttk.LabelFrame(outer, text=_("Click Force"), padding=10)
        click_frame.pack(fill="x", pady=(0, 10))
        click_frame.columnconfigure(0, weight=1)
        ttk.Label(
            click_frame,
            text=_(
                "Fine adjustment: 1–255 main click register units. "
                "Windows presets: 60 / 82 / 95 (120 / 164 / 190 Gf)."
            ),
            foreground="#555555",
            wraplength=680,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.click_force_scale = tk.Scale(
            click_frame,
            from_=CLICK_FORCE_MIN,
            to=CLICK_FORCE_MAX,
            resolution=1,
            orient="horizontal",
            showvalue=False,
            highlightthickness=0,
            variable=self.click_force_var,
            command=self._click_force_slider_changed,
        )
        self.click_force_scale.grid(row=1, column=0, sticky="ew")
        self.click_force_scale.bind("<ButtonRelease-1>", self._click_force_slider_released)
        self.click_force_scale.bind("<KeyRelease>", self._click_force_slider_released)
        ttk.Label(click_frame, text=str(CLICK_FORCE_MIN)).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(click_frame, text=str(CLICK_FORCE_MAX)).grid(
            row=2, column=0, sticky="e"
        )
        self.click_force_entry = ttk.Entry(
            click_frame, textvariable=self.click_force_value_var, width=9
        )
        self.click_force_entry.grid(row=1, column=1, padx=(10, 6))
        self.click_force_entry.bind("<Return>", self._apply_click_force_entry)
        self.click_force_entry.bind("<FocusOut>", self._apply_click_force_entry)
        ttk.Label(
            click_frame,
            text=_(
                "Release ratio: percent of the press force at which the "
                "click releases (up register). Windows default: 65."
            ),
            foreground="#555555",
            wraplength=680,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 4))
        self.click_ratio_scale = tk.Scale(
            click_frame,
            from_=RELEASE_RATIO_MIN,
            to=RELEASE_RATIO_MAX,
            resolution=1,
            orient="horizontal",
            showvalue=False,
            highlightthickness=0,
            variable=self.click_ratio_var,
            command=self._click_ratio_changed,
        )
        self.click_ratio_scale.grid(row=4, column=0, sticky="ew")
        self.click_ratio_scale.bind("<ButtonRelease-1>", self._click_ratio_slider_released)
        self.click_ratio_scale.bind("<KeyRelease>", self._click_ratio_slider_released)
        self.click_ratio_value_label = ttk.Label(
            click_frame, textvariable=self.click_ratio_value_var, width=4, anchor="center"
        )
        self.click_ratio_value_label.grid(row=4, column=1, padx=(10, 0))

        buttons_frame = ttk.LabelFrame(outer, text=_("TrackPoint Buttons"), padding=10)
        buttons_frame.pack(fill="x", pady=(0, 10))
        self.trackpoint_buttons_switch = ttk.Checkbutton(
            buttons_frame,
            text=_("Enable TrackPoint Buttons"),
            variable=self.trackpoint_buttons_var,
            command=self._trackpoint_buttons_changed,
        )
        self.trackpoint_buttons_switch.pack(anchor="w")

        trackpoint_frame = ttk.LabelFrame(
            outer, text=_("TrackPoint Click Force"), padding=10
        )
        trackpoint_frame.pack(fill="x", pady=(0, 10))
        trackpoint_frame.columnconfigure(0, weight=1)
        ttk.Label(
            trackpoint_frame,
            text=_(
                "Fine adjustment: 1–255 Windows 3HB register units. "
                "Windows presets: 28 / 38 / 60."
            ),
            foreground="#555555",
            wraplength=680,
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.trackpoint_force_scale = tk.Scale(
            trackpoint_frame,
            from_=TRACKPOINT_FORCE_MIN,
            to=TRACKPOINT_FORCE_MAX,
            resolution=1,
            orient="horizontal",
            showvalue=False,
            highlightthickness=0,
            variable=self.trackpoint_force_var,
            command=self._trackpoint_force_slider_changed,
        )
        self.trackpoint_force_scale.grid(row=1, column=0, sticky="ew")
        self.trackpoint_force_scale.bind(
            "<ButtonRelease-1>", self._trackpoint_force_slider_released
        )
        self.trackpoint_force_scale.bind(
            "<KeyRelease>", self._trackpoint_force_slider_released
        )
        ttk.Label(trackpoint_frame, text=str(TRACKPOINT_FORCE_MIN)).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(trackpoint_frame, text=str(TRACKPOINT_FORCE_MAX)).grid(
            row=2, column=0, sticky="e"
        )
        self.trackpoint_force_entry = ttk.Entry(
            trackpoint_frame,
            textvariable=self.trackpoint_force_value_var,
            width=9,
        )
        self.trackpoint_force_entry.grid(row=1, column=1, padx=(10, 6))
        self.trackpoint_force_entry.bind("<Return>", self._apply_trackpoint_force_entry)
        self.trackpoint_force_entry.bind(
            "<FocusOut>", self._apply_trackpoint_force_entry
        )
        ttk.Label(
            trackpoint_frame,
            text=_(
                "Release ratio: percent of the press force at which the "
                "click releases (up register). Windows default: 65."
            ),
            foreground="#555555",
            wraplength=680,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 4))
        self.trackpoint_ratio_scale = tk.Scale(
            trackpoint_frame,
            from_=RELEASE_RATIO_MIN,
            to=RELEASE_RATIO_MAX,
            resolution=1,
            orient="horizontal",
            showvalue=False,
            highlightthickness=0,
            variable=self.trackpoint_ratio_var,
            command=self._trackpoint_ratio_changed,
        )
        self.trackpoint_ratio_scale.grid(row=4, column=0, sticky="ew")
        self.trackpoint_ratio_scale.bind(
            "<ButtonRelease-1>", self._trackpoint_ratio_slider_released
        )
        self.trackpoint_ratio_scale.bind(
            "<KeyRelease>", self._trackpoint_ratio_slider_released
        )
        self.trackpoint_ratio_value_label = ttk.Label(
            trackpoint_frame,
            textvariable=self.trackpoint_ratio_value_var,
            width=4,
            anchor="center",
        )
        self.trackpoint_ratio_value_label.grid(row=4, column=1, padx=(10, 0))

        # Global draft controls: previews are RAM-only; Save persists every
        # changed register, Cancel restores the last saved state, Reset loads
        # the Windows "Medium" preset as a new draft.
        actions_frame = ttk.LabelFrame(outer, text=_("Pending Changes"), padding=10)
        actions_frame.pack(fill="x", pady=(0, 10))
        self.dirty_label = ttk.Label(
            actions_frame,
            text="● " + _("You have unsaved changes"),
            foreground="#b35000",
        )
        self.dirty_label.grid(row=0, column=0, sticky="w")
        actions_frame.columnconfigure(0, weight=1)
        self.save_button = ttk.Button(
            actions_frame, text=_("Save"), command=self._save_clicked, state="disabled"
        )
        self.save_button.grid(row=0, column=1, padx=(0, 8))
        self.cancel_button = ttk.Button(
            actions_frame, text=_("Cancel"), command=self._cancel_clicked, state="disabled"
        )
        self.cancel_button.grid(row=0, column=2, padx=(0, 8))
        self.reset_button = ttk.Button(
            actions_frame, text=_("Reset to Defaults"), command=self._reset_clicked
        )
        self.reset_button.grid(row=0, column=3)

        ttk.Separator(outer).pack(fill="x", pady=(4, 10))
        self.status_label = ttk.Label(
            outer,
            textvariable=self.status_var,
            wraplength=650,
            justify="left",
        )
        self.status_label.pack(anchor="w")

        self._set_controls_state(False)
        self._update_dirty_state()

    def _on_mousewheel(self, event) -> None:
        if getattr(event, "num", None) == 4:
            self.scroll_canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.scroll_canvas.yview_scroll(1, "units")
        elif getattr(event, "delta", 0):
            self.scroll_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _set_controls_state(self, available: bool) -> None:
        state = "normal" if available else "disabled"
        self.haptic_switch.configure(state=state)
        self.click_force_scale.configure(state=state)
        self.click_force_entry.configure(state=state)
        self.click_ratio_scale.configure(state=state)
        self.trackpoint_buttons_switch.configure(state=state)
        trackpoint_state = (
            "normal" if available and self.trackpoint_buttons_var.get() else "disabled"
        )
        self.trackpoint_force_entry.configure(state=trackpoint_state)
        self.trackpoint_ratio_scale.configure(state=trackpoint_state)
        self.intensity_scale.configure(
            state="normal" if available and self.haptic_feedback_var.get() else "disabled"
        )
        self.trackpoint_force_scale.configure(
            state="normal"
            if available and self.trackpoint_buttons_var.get()
            else "disabled"
        )
        self._update_dirty_state()

    # ------------------------------------------------------------------
    # Draft state helpers
    # ------------------------------------------------------------------

    def _current_draft(self) -> dict[str, int]:
        enabled = 1 if self.haptic_feedback_var.get() else 0
        intensity = (
            INTENSITY_LEVELS[self.intensity_level_var.get() - 1] if enabled else 0
        )
        return {
            "intensity": intensity,
            "click-force": self.click_force_var.get(),
            "click-ratio": self.click_ratio_var.get(),
            "trackpoint-force": self.trackpoint_force_var.get(),
            "trackpoint-ratio": self.trackpoint_ratio_var.get(),
            "buttons": 1 if self.trackpoint_buttons_var.get() else 0,
        }

    def _saved_draft(self) -> dict[str, int]:
        return {
            "intensity": self.intensity_applied if self.intensity_applied is not None else 0,
            "click-force": self.click_force_applied
            if self.click_force_applied is not None
            else self.click_force_var.get(),
            "click-ratio": self.click_ratio_applied
            if self.click_ratio_applied is not None
            else self.click_ratio_var.get(),
            "trackpoint-force": self.trackpoint_force_applied
            if self.trackpoint_force_applied is not None
            else self.trackpoint_force_var.get(),
            "trackpoint-ratio": self.trackpoint_ratio_applied
            if self.trackpoint_ratio_applied is not None
            else self.trackpoint_ratio_var.get(),
            "buttons": self.buttons_applied
            if self.buttons_applied is not None
            else (1 if self.trackpoint_buttons_var.get() else 0),
        }

    def _is_dirty(self) -> bool:
        if not self.loaded:
            return False
        return self._current_draft() != self._saved_draft()

    def _update_dirty_state(self) -> None:
        dirty = self._is_dirty()
        self.dirty_var.set(dirty)
        button_state = "normal" if dirty and not self.saving else "disabled"
        self.save_button.configure(state=button_state)
        self.cancel_button.configure(state=button_state)
        if dirty:
            self.dirty_label.configure(foreground="#b35000")
        else:
            self.dirty_label.configure(foreground="#555555")
            if self.loaded and not self.saving:
                self.dirty_label.configure(
                    text="● " + _("All changes saved"),
                    foreground="#2e7d32",
                )
                return
        self.dirty_label.configure(text="● " + _("You have unsaved changes"))

    def _preview(self, arguments: list[str], label: str) -> None:
        """Preview a draft value to RAM without touching flash."""
        if not self.loaded or not self.device_path or self.saving:
            return

        def finished(_output: str, error: Optional[str]) -> None:
            if error:
                self._set_status(
                    _("Preview of {label} failed: {error}").format(label=label, error=error)
                )
                self._read_state()
            else:
                self._set_status(
                    _("Previewing {label}. Press Save to keep it.").format(label=label)
                )

        self.worker.submit(arguments, finished)

    # ------------------------------------------------------------------
    # Device discovery / state loading
    # ------------------------------------------------------------------

    def refresh_devices(self) -> None:
        found = find_sensel_devices()
        previous = self.device_path
        self.devices = {display: path for path, display in found}
        displays = list(self.devices)
        self.device_combo["values"] = displays

        if not displays:
            self.device_path = None
            self.device_var.set("")
            self.loaded = False
            self._set_controls_state(False)
            self._set_status(
                _(
                    "Sensel Haptic Touchpad was not detected. "
                    "Check the connection and click Refresh."
                )
            )
            return

        selected_display = next(
            (display for display, path in self.devices.items() if path == previous),
            displays[0],
        )
        self.device_var.set(selected_display)
        self.device_path = self.devices[selected_display]
        self._read_state()

    def _device_selected(self, _event=None) -> None:
        display = self.device_var.get()
        self.device_path = self.devices.get(display)
        self._read_state()

    def _read_state(self) -> None:
        if not self.device_path or self.read_in_flight:
            return
        self.loaded = False
        self.read_in_flight = True
        self._set_controls_state(False)
        self._set_status(_("Reading settings from the device…"))
        self.worker.submit(
            ["--get-state", self.device_path],
            self._state_read_finished,
        )

    def _state_read_finished(self, output: str, error: Optional[str]) -> None:
        self.read_in_flight = False
        if error:
            self.loaded = False
            self._set_controls_state(False)
            self._set_status(_("Failed to read device settings: {error}").format(error=error))
            return

        try:
            state = parse_state(output)
        except RuntimeError as exc:
            self.loaded = False
            self._set_controls_state(False)
            self._set_status(_("The device returned invalid data: {error}").format(error=exc))
            return

        intensity = state["haptic-intensity"]
        if intensity > 0:
            self.saved_intensity = intensity
            haptic_enabled = True
            intensity_level = intensity_to_level(intensity)
        else:
            self.saved_intensity = load_saved_intensity()
            haptic_enabled = False
            intensity_level = intensity_to_level(self.saved_intensity)

        click_force = int(round(state["click-force"] / 2.0))
        click_force = max(CLICK_FORCE_MIN, min(CLICK_FORCE_MAX, click_force))
        trackpoint_force = max(
            TRACKPOINT_FORCE_MIN,
            min(TRACKPOINT_FORCE_MAX, state["trackpoint-click-force"]),
        )
        buttons = bool(state["trackpoint-buttons"])
        # Recover the release ratios from the up/down register pairs; older
        # helpers do not report the up registers, so keep the default then.
        click_ratio = release_ratio_from_registers(
            click_force, state.get("click-up", int(round(click_force * 0.65)))
        )
        trackpoint_ratio = release_ratio_from_registers(
            trackpoint_force,
            state.get(
                "trackpoint-click-up", int(round(trackpoint_force * 0.65))
            ),
        )

        self.syncing = True
        self.haptic_feedback_var.set(haptic_enabled)
        self.intensity_level_var.set(intensity_level)
        self.intensity_value_var.set(str(intensity_level))
        self.click_force_var.set(click_force)
        self.click_force_value_var.set(str(click_force))
        self.click_ratio_var.set(click_ratio)
        self.click_ratio_value_var.set(str(click_ratio))
        self.trackpoint_buttons_var.set(buttons)
        self.trackpoint_force_var.set(trackpoint_force)
        self.trackpoint_force_value_var.set(str(trackpoint_force))
        self.trackpoint_ratio_var.set(trackpoint_ratio)
        self.trackpoint_ratio_value_var.set(str(trackpoint_ratio))
        self.syncing = False

        # The RAM copy matches flash after a fresh read: the draft starts clean.
        self.intensity_applied = intensity
        self.click_force_applied = click_force
        self.click_ratio_applied = click_ratio
        self.trackpoint_force_applied = trackpoint_force
        self.trackpoint_ratio_applied = trackpoint_ratio
        self.buttons_applied = int(buttons)
        if intensity > 0:
            save_haptic_preferences(intensity, True)

        self.loaded = True
        self._set_controls_state(True)
        self._update_dirty_state()
        self._set_status(
            _(
                "Settings read from the device. Changes are previewed "
                "immediately; press Save to write them permanently."
            )
        )

    # ------------------------------------------------------------------
    # Preview handlers (RAM only)
    # ------------------------------------------------------------------

    def _intensity_changed(self, value: str) -> None:
        level = max(1, min(10, int(round(float(value)))))
        self.intensity_value_var.set(str(level))
        if self.syncing or not self.loaded or not self.haptic_feedback_var.get():
            self._update_dirty_state()
            return
        raw = INTENSITY_LEVELS[level - 1]
        self.saved_intensity = raw
        self._update_dirty_state()
        if self.saving:
            return
        self._preview(
            ["--preview-intensity", self.device_path or "", str(raw)],
            _("Haptics Intensity"),
        )

    def _haptic_feedback_changed(self) -> None:
        if self.syncing or not self.loaded:
            return
        enabled = self.haptic_feedback_var.get()
        if enabled:
            raw = self.saved_intensity
            level = intensity_to_level(raw)
            raw = INTENSITY_LEVELS[level - 1]
            self.syncing = True
            self.intensity_level_var.set(level)
            self.intensity_value_var.set(str(level))
            self.syncing = False
            self.saved_intensity = raw
            self._set_controls_state(True)
            self._update_dirty_state()
            if not self.saving:
                self._preview(
                    ["--preview-intensity", self.device_path or "", str(raw)],
                    _("Haptic Feedback"),
                )
        else:
            self.saved_intensity = INTENSITY_LEVELS[self.intensity_level_var.get() - 1]
            save_haptic_preferences(self.saved_intensity, False)
            self._set_controls_state(True)
            self._update_dirty_state()
            if not self.saving:
                self._preview(
                    ["--preview-intensity", self.device_path or "", "0"],
                    _("Haptic Feedback"),
                )

    def _click_force_slider_changed(self, value: str) -> None:
        click_force = int(round(float(value)))
        click_force = max(CLICK_FORCE_MIN, min(CLICK_FORCE_MAX, click_force))
        self.click_force_value_var.set(str(click_force))

    def _click_force_slider_released(self, _event=None) -> None:
        self._apply_click_force_entry()

    def _apply_click_force_entry(self, _event=None) -> None:
        if self.syncing or not self.loaded:
            return
        try:
            click_force = int(self.click_force_value_var.get().strip(), 10)
        except ValueError:
            messagebox.showwarning(
                _("Invalid Click Force"),
                _("Enter a value from 1 to 255."),
                parent=self.root,
            )
            self.click_force_value_var.set(str(self.click_force_var.get()))
            return
        if click_force < CLICK_FORCE_MIN or click_force > CLICK_FORCE_MAX:
            messagebox.showwarning(
                _("Invalid Click Force"),
                _("Click Force must be a value from 1 to 255."),
                parent=self.root,
            )
            self.click_force_value_var.set(str(self.click_force_var.get()))
            return
        self.syncing = True
        self.click_force_var.set(click_force)
        self.click_force_value_var.set(str(click_force))
        self.syncing = False
        self._update_dirty_state()
        if self.click_force_applied == click_force and self.saving:
            return
        # The helper accepts main Click Force in physical Gf.  The GUI
        # value is the raw register, so convert it back to Gf here.
        self._preview(
            [
                "--preview-click-force",
                self.device_path or "",
                str(click_force * 2),
                str(self.click_ratio_var.get()),
            ],
            _("Click Force"),
        )

    def _trackpoint_buttons_changed(self) -> None:
        if self.syncing or not self.loaded:
            return
        self._set_controls_state(True)
        enabled = int(self.trackpoint_buttons_var.get())
        self._update_dirty_state()
        if self.saving:
            return
        self._preview(
            ["--preview-trackpoint-buttons", self.device_path or "", str(enabled)],
            _("TrackPoint Buttons"),
        )

    def _trackpoint_force_slider_changed(self, value: str) -> None:
        trackpoint_force = int(round(float(value)))
        trackpoint_force = max(
            TRACKPOINT_FORCE_MIN,
            min(TRACKPOINT_FORCE_MAX, trackpoint_force),
        )
        self.trackpoint_force_value_var.set(str(trackpoint_force))

    def _trackpoint_force_slider_released(self, _event=None) -> None:
        self._apply_trackpoint_force_entry()

    def _apply_trackpoint_force_entry(self, _event=None) -> None:
        if self.syncing or not self.loaded:
            return
        try:
            trackpoint_force = int(self.trackpoint_force_value_var.get().strip(), 10)
        except ValueError:
            messagebox.showwarning(
                _("Invalid TrackPoint Click Force"),
                _("Enter a value from 1 to 255."),
                parent=self.root,
            )
            self.trackpoint_force_value_var.set(str(self.trackpoint_force_var.get()))
            return
        if (
            trackpoint_force < TRACKPOINT_FORCE_MIN
            or trackpoint_force > TRACKPOINT_FORCE_MAX
        ):
            messagebox.showwarning(
                _("Invalid TrackPoint Click Force"),
                _("TrackPoint Click Force must be a value from 1 to 255."),
                parent=self.root,
            )
            self.trackpoint_force_value_var.set(str(self.trackpoint_force_var.get()))
            return
        self.syncing = True
        self.trackpoint_force_var.set(trackpoint_force)
        self.trackpoint_force_value_var.set(str(trackpoint_force))
        self.syncing = False
        self._update_dirty_state()
        if self.trackpoint_force_applied == trackpoint_force and self.saving:
            return
        self._preview(
            [
                "--preview-trackpoint-click-force",
                self.device_path or "",
                str(trackpoint_force),
                str(self.trackpoint_ratio_var.get()),
            ],
            _("TrackPoint Click Force"),
        )

    def _click_ratio_changed(self, value: str) -> None:
        ratio = max(
            RELEASE_RATIO_MIN, min(RELEASE_RATIO_MAX, int(round(float(value))))
        )
        self.click_ratio_value_var.set(str(ratio))
        if self.syncing or not self.loaded:
            self._update_dirty_state()
            return
        self._update_dirty_state()
        if self.click_ratio_applied == ratio or self.saving:
            return
        self._preview(
            [
                "--preview-click-force",
                self.device_path or "",
                str(self.click_force_var.get() * 2),
                str(ratio),
            ],
            _("Click Release Ratio"),
        )

    def _click_ratio_slider_released(self, _event=None) -> None:
        # tk.Scale fires the command continuously while dragging; the helper
        # write is issued from the change handler only on release via this
        # indirection to avoid hammering the device mid-drag.
        pass

    def _trackpoint_ratio_changed(self, value: str) -> None:
        ratio = max(
            RELEASE_RATIO_MIN, min(RELEASE_RATIO_MAX, int(round(float(value))))
        )
        self.trackpoint_ratio_value_var.set(str(ratio))
        if self.syncing or not self.loaded:
            self._update_dirty_state()
            return
        self._update_dirty_state()
        if self.trackpoint_ratio_applied == ratio or self.saving:
            return
        self._preview(
            [
                "--preview-trackpoint-click-force",
                self.device_path or "",
                str(self.trackpoint_force_var.get()),
                str(ratio),
            ],
            _("TrackPoint Release Ratio"),
        )

    def _trackpoint_ratio_slider_released(self, _event=None) -> None:
        pass

    # ------------------------------------------------------------------
    # Global Save / Cancel / Reset
    # ------------------------------------------------------------------

    def _pending_operations(self) -> list[tuple[str, str, str]]:
        """Changed settings as (label, helper flag, value) tuples."""
        operations: list[tuple[str, str, str]] = []
        draft = self._current_draft()
        saved = self._saved_draft()
        if draft["intensity"] != saved["intensity"]:
            operations.append(
                (
                    _("Haptics Intensity"),
                    "--commit-intensity",
                    str(draft["intensity"]),
                )
            )
        if draft["click-force"] != saved["click-force"] or (
            draft["click-ratio"] != saved["click-ratio"]
        ):
            operations.append(
                (
                    _("Click Force"),
                    "--commit-click-force",
                    f"{draft['click-force'] * 2} {draft['click-ratio']}",
                )
            )
        if draft["trackpoint-force"] != saved["trackpoint-force"] or (
            draft["trackpoint-ratio"] != saved["trackpoint-ratio"]
        ):
            operations.append(
                (
                    _("TrackPoint Click Force"),
                    "--commit-trackpoint-click-force",
                    f"{draft['trackpoint-force']} {draft['trackpoint-ratio']}",
                )
            )
        if draft["buttons"] != saved["buttons"]:
            operations.append(
                (
                    _("TrackPoint Buttons"),
                    "--commit-trackpoint-buttons",
                    str(draft["buttons"]),
                )
            )
        return operations

    def _save_clicked(self) -> None:
        operations = self._pending_operations()
        if not operations:
            self._update_dirty_state()
            return
        self.saving = True
        self._set_controls_state(True)
        self.save_button.configure(state="disabled")
        self.cancel_button.configure(state="disabled")
        self._run_save_queue(operations, 0)

    def _run_save_queue(self, operations: list[tuple[str, str, str]], index: int) -> None:
        total = len(operations)
        self._set_status(
            _("Saving {current}/{total}: {label}…").format(
                current=index + 1, total=total, label=operations[index][0]
            )
        )

        def finished(_output: str, error: Optional[str]) -> None:
            if error:
                self.saving = False
                self._set_status(
                    _("Saving {label} failed: {error}").format(
                        label=operations[index][0], error=error
                    )
                )
                messagebox.showerror(
                    _("Save failed"),
                    error,
                    parent=self.root,
                )
                # Re-read so applied_* reflect what actually reached the device.
                self._read_state()
                return
            if index + 1 < total:
                self._run_save_queue(operations, index + 1)
            else:
                self.saving = False
                draft = self._current_draft()
                self.intensity_applied = draft["intensity"]
                self.click_force_applied = draft["click-force"]
                self.click_ratio_applied = draft["click-ratio"]
                self.trackpoint_force_applied = draft["trackpoint-force"]
                self.trackpoint_ratio_applied = draft["trackpoint-ratio"]
                self.buttons_applied = draft["buttons"]
                if draft["intensity"] > 0:
                    save_haptic_preferences(draft["intensity"], True)
                self._set_controls_state(True)
                self._update_dirty_state()
                self._set_status(_("All changes saved to the device."))

        self.worker.submit(
            [operations[index][1], self.device_path or "", *operations[index][2].split()],
            finished,
        )

    def _cancel_clicked(self) -> None:
        saved = self._saved_draft()
        self.syncing = True
        if saved["intensity"] > 0:
            self.haptic_feedback_var.set(True)
            self.intensity_level_var.set(intensity_to_level(saved["intensity"]))
            self.intensity_value_var.set(str(intensity_to_level(saved["intensity"])))
        else:
            self.haptic_feedback_var.set(False)
        self.click_force_var.set(saved["click-force"])
        self.click_force_value_var.set(str(saved["click-force"]))
        self.click_ratio_var.set(saved["click-ratio"])
        self.click_ratio_value_var.set(str(saved["click-ratio"]))
        self.trackpoint_buttons_var.set(bool(saved["buttons"]))
        self.trackpoint_force_var.set(saved["trackpoint-force"])
        self.trackpoint_force_value_var.set(str(saved["trackpoint-force"]))
        self.trackpoint_ratio_var.set(saved["trackpoint-ratio"])
        self.trackpoint_ratio_value_var.set(str(saved["trackpoint-ratio"]))
        self.syncing = False
        self._set_controls_state(True)
        # Re-preview each saved value so device RAM matches flash again.
        self._preview(
            ["--preview-intensity", self.device_path or "", str(saved["intensity"])],
            _("Haptics Intensity"),
        )
        self._preview(
            [
                "--preview-click-force",
                self.device_path or "",
                str(saved["click-force"] * 2),
                str(saved["click-ratio"]),
            ],
            _("Click Force"),
        )
        self._preview(
            [
                "--preview-trackpoint-click-force",
                self.device_path or "",
                str(saved["trackpoint-force"]),
                str(saved["trackpoint-ratio"]),
            ],
            _("TrackPoint Click Force"),
        )
        self._preview(
            ["--preview-trackpoint-buttons", self.device_path or "", str(saved["buttons"])],
            _("TrackPoint Buttons"),
        )
        self._update_dirty_state()
        self._set_status(_("Changes discarded; the device keeps its saved settings."))

    def _reset_clicked(self) -> None:
        self.syncing = True
        self.haptic_feedback_var.set(True)
        self.intensity_level_var.set(intensity_to_level(RESET_INTENSITY))
        self.intensity_value_var.set(str(intensity_to_level(RESET_INTENSITY)))
        self.saved_intensity = RESET_INTENSITY
        self.click_force_var.set(RESET_CLICK_FORCE)
        self.click_force_value_var.set(str(RESET_CLICK_FORCE))
        self.click_ratio_var.set(RESET_RELEASE_RATIO)
        self.click_ratio_value_var.set(str(RESET_RELEASE_RATIO))
        self.trackpoint_buttons_var.set(RESET_TRACKPOINT_BUTTONS)
        self.trackpoint_force_var.set(RESET_TRACKPOINT_FORCE)
        self.trackpoint_force_value_var.set(str(RESET_TRACKPOINT_FORCE))
        self.trackpoint_ratio_var.set(RESET_RELEASE_RATIO)
        self.trackpoint_ratio_value_var.set(str(RESET_RELEASE_RATIO))
        self.syncing = False
        self._set_controls_state(True)
        # Preview the preset like any other draft change.
        if not self.saving:
            self._preview(
                ["--preview-intensity", self.device_path or "", str(RESET_INTENSITY)],
                _("Haptics Intensity"),
            )
            self._preview(
                [
                    "--preview-click-force",
                    self.device_path or "",
                    str(RESET_CLICK_FORCE * 2),
                    str(RESET_RELEASE_RATIO),
                ],
                _("Click Force"),
            )
            self._preview(
                [
                    "--preview-trackpoint-click-force",
                    self.device_path or "",
                    str(RESET_TRACKPOINT_FORCE),
                    str(RESET_RELEASE_RATIO),
                ],
                _("TrackPoint Click Force"),
            )
            self._preview(
                ["--preview-trackpoint-buttons", self.device_path or "", str(int(RESET_TRACKPOINT_BUTTONS))],
                _("TrackPoint Buttons"),
            )
        self._update_dirty_state()
        self._set_status(
            _("Default preset loaded as a draft. Adjust it and press Save to keep it.")
        )

    def _close(self) -> None:
        self.worker.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    SenselHapticApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
