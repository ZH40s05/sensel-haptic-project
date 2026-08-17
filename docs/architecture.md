# Architecture

The project is a userspace integration for one family of Sensel haptic
touchpads. It is deliberately separate from the Linux kernel input path:
libinput and the kernel continue to deliver pointer, gesture, and button
events, while this project changes device settings through the Sensel HID
register pipe.

```mermaid
flowchart LR
    gui[Standalone Tk control panel]
    settings[Patched GNOME Settings panel]
    auth[pkexec and Polkit]
    helper[Root-owned sensel-haptic-set]
    daemon[sensel-haptic-daemon]
    hid[/dev/hidrawN]
    device[Sensel haptic touchpad]

    gui --> auth
    settings --> auth
    auth --> helper
    helper --> daemon
    daemon --> hid
    hid --> device
```

## Components

### `scripts/sensel-haptic-daemon`

This is the privileged protocol implementation. It validates the hidraw path,
checks the Sensel sysfs identity, serializes access with a lock file, frames
21-byte report-ID `0x09` HID reports, checks response checksums, and verifies
important writes by reading the registers back.

The daemon also owns the user-facing register operations:

- haptic intensity;
- main click force;
- TrackPoint button click force;
- TrackPoint button enablement;
- persistence through the Sensel `UserSetting` register.

### `scripts/sensel-haptic-set`

This is the narrow command dispatcher used by Polkit. It rejects unexpected
arguments before handing an operation to the daemon. Keeping this validation
at the privileged boundary is important because GUI input must not be treated
as trusted.

### `tools/sensel_haptic_gui.py`

The standalone panel is a Tk application. It discovers matching hidraw nodes,
uses `pkexec` to invoke the helper, and performs operations asynchronously so
the UI remains responsive while the device is being queried.

### `patches/sensel-gnome-control-center.patch`

This optional patch adds Sensel-specific rows to the GNOME Control Center
mouse panel. It is a distribution integration layer, not a generic GNOME or
libinput API. The patch currently targets the GNOME Control Center 50.0 source
layout and therefore must be rebased whenever the upstream panel changes.

### `tools/sensel-hid-pipe.py`

This is a developer diagnostic tool. It exposes raw register reads and
explicitly opt-in writes for protocol investigation. It should not be used as
the normal desktop configuration entry point.

## Privilege boundary

The GUI and GNOME panel are unprivileged. The normal configuration path opens
the hidraw node only in the helper and daemon. The diagnostic tool can also
open it, but only as an explicitly invoked developer operation. The Polkit
rule grants the active local `wheel` user permission to invoke the installed
helper; the helper still validates the device, operation, and value itself.

The project does not attempt to replace libinput or the kernel driver. A
future upstreamable design would keep this device-specific backend separate
from generic pointer-event handling and would expose a stable system API to
desktop settings instead of embedding private register access in a desktop
panel.
