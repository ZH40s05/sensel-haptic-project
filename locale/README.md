# Sensel Haptic Touchpad translations

The standalone control panel uses the gettext domain
`sensel-haptic-control`. Translation sources live under:

```text
locale/<language>/LC_MESSAGES/sensel-haptic-control.po
```

The GUI uses the system locale by default. `SENSEL_HAPTIC_LOCALE` can be set
for testing a specific language, and `SENSEL_HAPTIC_LOCALEDIR` can point to a
development translation directory. The installer validates each PO file,
compiles it to an MO catalog, and installs it under `/usr/share/locale`.

English is the source-language fallback. New translations can be generated
from the GUI source with:

```sh
xgettext --language=Python --from-code=UTF-8 --keyword=_ \
  --output=locale/sensel-haptic-control.pot tools/sensel_haptic_gui.py
```
