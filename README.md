# Disk Optimizer Pro

A small Windows 10/11 desktop utility for reviewing local drive space, checking physical memory use, and clearing selected temporary files. It discovers drives on the current computer instead of assuming that a `D:` drive exists.

## What it does

- Shows free space for the system drive and another available local drive, plus physical RAM usage.
- Opens Windows Task Manager so you can identify memory-heavy apps. The app does not force-close apps or use unsafe “RAM cleaner” tricks.
- Starts with three low-risk choices: this user's temp files, Windows temp files, and rebuildable thumbnail cache. Each run presents a review prompt.
- Keeps browser, developer, update, diagnostic, Recycle Bin, and other-drive cleanup optional. Browser history, saved passwords, and personal documents are not cleanup targets.
- Includes optional large-file, duplicate-file, and empty-folder scans. Scans default to a limited user/system location; choose another detected drive when needed.

System-level cleanup can be limited by Windows permissions. The app runs normally without administrator rights; use the explicit elevation control only when a selected action requires it. Avoid removing diagnostic dumps if you need them to investigate a crash. Deleting the Recycle Bin is permanent.

## Run from source

Requirements: Windows 10/11 and Python 3.10 or newer.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

The included `launch_disk_optimizer.vbs` can launch the source version without a console window. A Python runtime and the requirements must be installed for this source-based option.

## Make a portable ZIP for another PC

On a Windows build computer, run:

```text
build_portable.bat
```

The script creates `dist\DiskOptimizerPro`. Zip the **entire folder**, including the executable and its companion files, and extract that folder on the receiving Windows 10/11 PC. Launch `DiskOptimizerPro.exe` (or the included VBS launcher). The receiving PC does not need Python or a separate dependency installation. Build the package on Windows for Windows; do not copy only the `.exe`.

The app detects drives, Windows folders, and the signed-in user's profile on the receiving PC at runtime. It does not rely on the developer's drive layout or account paths.

## Tests

Run the unit tests on Windows with the app dependencies installed:

```powershell
python -m unittest discover -s tests -v
```

## Project layout

- `gui/` — CustomTkinter user interface
- `engine/` — Windows telemetry, safe cleanup helpers, and file scanners
- `tests/` — unit and GUI-instantiation tests
- `build_portable.bat` — self-contained Windows folder-package build

## License

MIT. See [LICENSE](LICENSE).
