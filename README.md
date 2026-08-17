# Sensel Haptic Touchpad for GNOME

Community integration for the Sensel haptic touchpad found in selected
ThinkPad systems. It provides a standalone Tk control panel and an optional
GNOME Settings integration for Fedora.

This project writes private Sensel HID registers. It is experimental hardware
integration software, not an official Sensel or GNOME release.

## Features

- Read and write haptic feedback intensity.
- Configure main click force and TrackPoint button click force.
- Enable or disable TrackPoint buttons.
- Use the same root-owned helper from the standalone GUI and GNOME Settings.
- Include Simplified Chinese and Traditional Chinese translations.
- Keep register validation and device identification in the privileged helper.

## Supported environment

The tested target is Fedora with GNOME Control Center 50.0 and a Sensel HID
device identified by VID/PID 2C2F:0028 or an SNSL device path.

The standalone panel needs:

- Python 3.9 or newer;
- Tk;
- gettext runtime support;
- sudo, pkexec, and Polkit for privileged writes.

The GNOME Settings build additionally needs the Fedora GNOME development
packages, Meson, Ninja, Blueprint Compiler, and a working C compiler. The
installer can install the known Fedora build dependencies, but the exact
package set depends on the installed Fedora release.

## Installation

### Standalone control panel

Run from the repository root:

    ./install-sensel-haptic-gui.sh

The installer installs the helper, daemon, Polkit rule, desktop launcher, and
translation catalogs under system directories. It does not require building
GNOME Control Center.

### GNOME Settings integration

Run:

    ./install-sensel-gnome-settings.sh

If a local GNOME source tree is not available, the installer downloads the
GNOME Control Center 50.0 source archive from download.gnome.org, verifies its
SHA-256 checksum, extracts it under the ignored build directory, applies the
patch, and builds it. The script asks for confirmation before installing the
modified GNOME Settings binary.

Useful overrides:

    SENSEL_GNOME_SOURCE_DIR=/path/to/gnome-control-center-50.0 ./install-sensel-gnome-settings.sh
    SENSEL_GNOME_SOURCE_ARCHIVE=/path/to/gnome-control-center-50.0.tar.xz ./install-sensel-gnome-settings.sh
    SENSEL_GNOME_BUILD_DIR=/path/to/build ./install-sensel-gnome-settings.sh

The source checksum can be overridden for a different, locally reviewed
source archive with SENSEL_GNOME_SOURCE_SHA256. Set it to an empty value only
when the archive is trusted and verified by another method.

To restore the distribution GNOME Settings package after testing:

    sudo dnf5 reinstall gnome-control-center

## Safety and device access

The helper runs as root because the Sensel HID register interface is exposed
through hidraw. It rejects unexpected paths and non-Sensel devices, validates
all values, serializes access with a lock file, and checks write readback.

The Polkit rule grants the local active wheel group permission to invoke only
the installed helper. Review this policy before installing it on a shared
machine. Private register writes can change the feel or behavior of the
touchpad; record current values before experimenting.

The install scripts modify system files under /usr/local, /usr/share, and
/etc/polkit-1. They are intended for Fedora systems where the user can review
and revert those changes.

## Repository layout

    install-sensel-haptic-gui.sh       Standalone panel installer
    install-sensel-gnome-settings.sh   GNOME Settings build and installer
    scripts/                           Root helper, daemon, and Polkit rule
    tools/                             GUI, HID diagnostic tool, and launcher
    patches/                           GNOME Control Center patch
    locale/                            Gettext translation sources
    docs/                              Architecture, protocol, and project notes
    tests/                             Hardware-independent checks and unit tests

The local source, artifacts, build directories, source archives, RPMs,
generated catalogs, and Windows application files are deliberately excluded
by .gitignore. They may exist in a working copy for investigation, but they
are not part of a public checkout.

## Development and checks

Run the hardware-independent checks before submitting changes:

    ./tests/check.sh

The checks cover shell syntax, Python syntax, protocol behavior, gettext
catalogs, and the desktop entry when the corresponding validation tools are
installed. They do not access hardware or perform register writes.

More project information is available in:

- [Architecture](docs/architecture.md)
- [Compatibility and limitations](docs/compatibility.md)
- [Upstreaming plan](docs/upstreaming.md)

The GNOME patch is based on the upstream 50.0 source layout. When updating
GNOME, first obtain a clean upstream source tree, rebase or regenerate the
patch, build it locally, and update the documented checksum and compatibility
notes together.

## Translations

Translation sources are under locale. To generate a template from the GUI:

    xgettext --language=Python --from-code=UTF-8 --keyword=_ --output=locale/sensel-haptic-control.pot tools/sensel_haptic_gui.py

English is the fallback language. SENSEL_HAPTIC_LOCALE and
SENSEL_HAPTIC_LOCALEDIR can be used to test a specific catalog without
installing it system-wide.

## Reverse-engineering notes

docs/sensel-windows-reverse-engineering.md records the register mapping and
HID framing used by the implementation. The proprietary Windows application
and its runtime files are not redistributed by this repository.

## License

Original project code is licensed under GPL-2.0-or-later; see LICENSE.
GNOME Control Center and other upstream components retain their own license
notices. See NOTICE.md for the public-repository boundary and trademark note.
