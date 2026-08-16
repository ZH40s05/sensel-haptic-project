# Contributing

Contributions are welcome, especially device compatibility reports, fixes for
the Fedora/GNOME integration, and translations.

Before opening a pull request:

1. Run ./tests/check.sh.
2. Do not commit source/, artifacts/, build directories, Windows application
   files, or generated translation catalogs.
3. For changes to the GNOME integration, keep the patch based on the GNOME
   Control Center version documented in README.md.
4. Do not test register writes on an unfamiliar device. The helper is
   intentionally restricted to Sensel HID devices, but hardware behavior can
   still vary by firmware.

Keep commits focused and describe any device, firmware, Fedora, or GNOME
version used for validation.
