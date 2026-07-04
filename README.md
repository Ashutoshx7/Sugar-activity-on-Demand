# Sugar Activity Studio

Generate real, installable [Sugar](https://sugarlabs.org) learning activities
from a plain-language idea — outside the Sugar shell, as a standalone desktop
app.

This is the standalone extraction of the **Activity on Demand** project: the
same create → preview → refine → export flow that runs embedded in the Sugar
shell fork, with the identical backend (planning, RAG over installed Sugar
activities, LLM code generation, validation, XO packaging, Flatpak export).

## What it does

- Opens on **Your activities** — Sugar's classic home view: your XO icon
  in the center (in your own colors) with everything you have generated
  (from `~/.sugar/default/aod/projects/`) ringed around it, using the
  same ring/spiral geometry as the Sugar shell. Click an icon to play the
  activity in its own window; hover or right-click for **Open** /
  **Modify** (reopen in the studio with full version history and
  refinement chat); click the center XO to create something new.
- Describe an activity in your own words; the studio plans and generates a
  complete Sugar activity (`activity.py`, `setup.py`, `activity.info`, icon,
  license, README).
- Live preview of the generated activity, with click-to-target refinement
  chat.
- Export as an installable `.xo` bundle or buildable Flatpak sources.
- Install & Open: installs into `~/Activities` and launches the activity with
  `sugar-activity3` — no Sugar shell needed.

## System requirements

Python packages from PyPI are not enough — the GTK stack comes from your
distribution:

- Python ≥ 3.8
- GTK 3 + PyGObject (`python3-gi`, `gir1.2-gtk-3.0`)
- Sugar toolkit (`python3-sugar3` / sucrose packages) — provides the `sugar3`
  Python package and the `sugar-activity3` launcher

On Debian/Ubuntu:

```sh
sudo apt install python3-gi gir1.2-gtk-3.0 python3-sugar3 sugar-toolkit-gtk3
```

## Run

From a checkout (no install needed):

```sh
python3 bin/sugar-aod-studio
# or
python3 -m aodstudio
```

Installed (`pip install .`):

```sh
sugar-aod-studio
```

## Tests

```sh
python3 -m pytest tests/ -q
```

## Notes

- The studio stores projects, sessions, and credentials under
  `~/.sugar/default/aod` — the same store the Sugar shell integration uses,
  so activities generated here appear there too (and vice versa).
- Origin: extracted from the `aod-activity-on-demand` branch of the
  [Sugar fork](https://github.com/Ashutoshx7/sugar).

## License

GPL-3.0-or-later, same as Sugar. See [LICENSE](LICENSE).
