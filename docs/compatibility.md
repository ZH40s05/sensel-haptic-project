# Compatibility and limitations

This project is intentionally conservative about device matching. A Sensel
brand name alone is not sufficient to establish protocol compatibility: the
implementation relies on a particular HID report layout and private register
map.

## Known target

The currently validated target is the Sensel haptic touchpad exposed as:

- USB identity `2C2F:0028`;
- an `SNSL0028` hidraw/sysfs path;
- a Linux `/dev/hidrawN` character device.

The documented desktop target is Fedora GNOME with the GNOME Control Center
50.0 source layout. The standalone panel is independent of GNOME Control
Center, but still expects Python 3.9 or newer, Tk, `pkexec`, and Polkit.

## Validation levels

| Area | Current status |
| --- | --- |
| Protocol framing and range checks | Covered by hardware-independent unit tests |
| Shell, Python, translations, desktop entry | Covered by `tests/check.sh` when optional tools are installed |
| Standalone panel | Validated manually on the target device |
| GNOME Settings patch | Validated against the documented GNOME 50.0 source layout |
| Other Sensel touchpads | Not guaranteed; requires a compatibility report |
| Suspend/resume, multiple devices, and firmware upgrades | Not covered by automated tests |

## Adding a compatibility report

Please record the following before proposing support for another device:

1. exact laptop and touchpad model;
2. kernel and distribution versions;
3. GNOME/KDE or other desktop version;
4. firmware version, if available;
5. the resolved `/sys/class/hidraw/hidrawN` path;
6. read-only register observations;
7. whether settings survive reboot and suspend/resume.

Do not test writes on an unfamiliar device until the register map and safe
rollback procedure are understood.
