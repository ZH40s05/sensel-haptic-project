# Security policy

This project installs a root-owned HID helper and a Polkit rule. A mistake in
either can affect hardware settings or expand local privilege, so security
reports should not be posted publicly with an exploit before a fix is
available.

Until a public security contact is configured, send a private report to the
repository maintainer and include:

- the affected commit or release;
- Fedora, kernel, GNOME, and device firmware versions;
- reproduction steps that do not include secrets;
- the expected and observed behavior.

Do not run the installer on a production workstation without reviewing the
files installed under /usr/local/libexec and /etc/polkit-1/rules.d.
