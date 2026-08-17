# Upstreaming plan

The repository is suitable as an independent community project, but the
current tree is a Fedora-specific integration bundle rather than a patch that
can be submitted unchanged to one upstream project.

## Recommended order

### 1. Stabilize the independent project

- keep the Sensel protocol implementation in userspace;
- document the exact device and firmware boundary;
- add fake-device tests for framing, range validation, persistence, and
  readback failures;
- publish reproducible checks and a Fedora package;
- collect reports from more than one device and firmware revision.

### 2. Submit the right layer to the right project

| Target | Suitable contribution |
| --- | --- |
| Linux kernel HID | A small device quirk or standard HID haptic mapping, if the device exposes a stable standard interface |
| libinput | Pointer, pressure, gesture, or button behavior that belongs in the input backend |
| GNOME Control Center | A generic settings UI backed by a stable system API, not direct Sensel register access |
| Fedora | An RPM, dependency metadata, Polkit integration, and desktop integration |

The Python daemon, private register map, Fedora installer, and GNOME patch
should remain project-specific until a lower-level upstream API exists.

## Review checklist before an upstream proposal

- state the user-visible problem and affected devices;
- separate protocol, security, packaging, and UI changes into different
  commits;
- include logs and read-only observations, not proprietary application files;
- test hotplug, permission errors, malformed replies, and suspend/resume;
- rebase the GNOME patch onto the current upstream source before proposing it;
- include the appropriate sign-off and contribution provenance.
