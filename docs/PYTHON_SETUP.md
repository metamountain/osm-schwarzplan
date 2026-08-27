# Installing Python — a beginner's guide

**New to Python? Never installed it? Start here.** This tool is a small Python
program. You need Python on your computer once; after that, running OSM
Schwarzplan takes one double-click. No programming knowledge required.

- [What you need (in one sentence)](#what-you-need-in-one-sentence)
- [Windows](#windows)
- [macOS](#macos)
- [Linux](#linux)
- [Running the tool](#running-the-tool)
- [Do I need to install anything else? (ezdxf, Pillow)](#do-i-need-to-install-anything-else-ezdxf-pillow)
- [Troubleshooting](#troubleshooting)

## What you need (in one sentence)

**Python 3.8 or newer**, with the standard **Tkinter** window library (included
automatically on Windows and macOS). Everything else the tool installs by
itself the first time you use it.

---

## Windows

1. Go to **<https://www.python.org/downloads/>** and click the big
   **“Download Python”** button.
2. Run the downloaded installer.
3. **VERY IMPORTANT:** on the first screen, tick the box
   **“Add python.exe to PATH”** at the bottom, *then* click **Install Now**.

   ![Tick "Add python.exe to PATH"] — if you miss this, Windows won't find
   Python and you'll see *“python is not recognized”* later. (You can re-run the
   installer and choose *Modify* to fix it.)
4. When it finishes, click **Close**. Tkinter is already included — nothing more
   to install.
5. **Check it worked:** press `Win + R`, type `cmd`, press Enter, then type:

   ```
   python --version
   ```

   You should see something like `Python 3.12.4`. Done.

> No admin rights? The python.org installer offers a per-user install that
> doesn't need an administrator.

---

## macOS

1. Go to **<https://www.python.org/downloads/macos/>** and download the latest
   **macOS 64-bit universal2 installer**.
2. Open the `.pkg` file and follow the steps. Tkinter is included.
3. **Check it worked:** open **Terminal** (Spotlight → type “Terminal”) and run:

   ```
   python3 --version
   ```

   You should see `Python 3.x.x`.

> Prefer Homebrew? `brew install python-tk` also gives you Python **with**
> Tkinter. The Apple-provided system Python is not recommended.

---

## Linux

Most distributions ship Python 3, but **Tkinter is often a separate package**.
Install both:

| Distribution | Command |
| --- | --- |
| Ubuntu / Debian / Mint | `sudo apt install python3 python3-tk python3-pip` |
| Fedora | `sudo dnf install python3 python3-tkinter python3-pip` |
| Arch / Manjaro | `sudo pacman -S python tk` |
| openSUSE | `sudo zypper install python3 python3-tk python3-pip` |

Check it worked:

```
python3 --version
```

---

## Running the tool

First download this project: on the GitHub page click the green **Code**
button → **Download ZIP**, then unzip it. (Or `git clone` it if you use Git.)

- **Windows — the easy way:** double-click **`run.bat`**. The window opens.
  You can also **drag an `.osm` file onto `run.bat`** to load it immediately.
- **Any system — from a terminal**, inside the project folder:

  ```
  python osm_schwarzplan.py
  ```
  (On macOS/Linux use `python3` if `python` isn't found.)

Then click **Open file…**, choose an `.osm` file (a `sample.osm` is included to
try right away), and use **Export…** to save DXF, SVG, or PNG.

Where do `.osm` files come from? See the
[“Getting OpenStreetMap data”](../README.md#getting-openstreetmap-data) section
of the README.

---

## Do I need to install anything else? (ezdxf, Pillow)

**Usually no — the tool handles it.** The first time you export:

- **DXF** export needs a package called **`ezdxf`**,
- **PNG** export needs **`Pillow`**.

If either is missing, OSM Schwarzplan installs it automatically (you'll see a
short `[Setup] …` message). **SVG** export and the preview need nothing extra.

Want to install them yourself ahead of time? In the project folder run:

```
pip install -r requirements.txt
```

(Use `pip3` on macOS/Linux if `pip` isn't found.) To stop the tool from
auto-installing anything, start it with `--no-install`.

---

## Troubleshooting

**“python is not recognized as an internal or external command” (Windows)**
Python isn't on your PATH. Re-run the python.org installer, choose **Modify**,
and make sure **“Add python.exe to PATH”** is ticked. Then open a *new* command
window and try again. As a quick alternative, try the `py` launcher:
`py osm_schwarzplan.py`.

**`ModuleNotFoundError: No module named 'tkinter'` (mostly Linux)**
Tkinter isn't installed. Install it with your distribution's package (see the
[Linux](#linux) table, e.g. `sudo apt install python3-tk`).

**“Could not install ezdxf / Pillow” or you're offline / behind a proxy**
The auto-install needs internet. On a restricted network, either install the
packages manually with `pip install -r requirements.txt` (once you have
access), or just use **SVG** export, which requires no extra packages. You can
also run with `--no-install` to skip the attempt.

**Double-clicking `run.bat` flashes a black window and closes**
That usually means Python isn't installed or isn't on PATH — see the first item.
`run.bat` is set to pause on error so you can read the message; if it still
closes instantly, run `python osm_schwarzplan.py` from a command window to see
the full error.

**`pip` is not recognized**
Use `python -m pip install -r requirements.txt` instead (that always works if
Python is installed).

---

Still stuck? Open an issue on the
[project's GitHub page](https://github.com/metamountain/osm-schwarzplan/issues)
with the exact error message and your operating system.
