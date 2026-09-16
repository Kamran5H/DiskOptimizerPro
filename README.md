# Disk Optimizer Pro V2 - Kamran Ashraf

An executive, high-performance Windows disk optimization and cleanup suite built to monitor and clean **both Local Disk C: and Local Disk D:** using automated, thoroughly-tested multi-threaded routines.

---

## What's New in V2

1. **Full Local Disk D: Support & Dual-Drive Telemetry**:
   - Live side-by-side capacity, free space, and usage meters for **Drive C:** (~12 GB free) and **Drive D:** (~31 GB free).
   - **Target Scope Selector**: Choose between `All Drives (C: & D:)`, `Drive C: Only`, or `Drive D: Only`.
   - **D: Root VC++ Junk Cleaner**: Sweeps classic Visual C++ extraction leftovers (`eula.*.txt`, `install.*`, `VC_RED.*`, `globdata.ini`).
   - **D: Developer Caches**: Cleans Python `__pycache__` and `.pytest_cache` directories on D:.
   - **Multi-Drive Recycle Bin**: Empties `$RECYCLE.BIN` across all attached local drives.
   - **Multi-Drive Shadow Storage**: Resizes shadow storage to 3% max on both C: and D: via `vssadmin`.

2. **Advanced System & Developer Optimizers**:
   - **Windows Delivery Optimization Cache**: Cleans cached peer-to-peer Windows update files.
   - **Windows Prefetch Cache**: Cleans obsolete prefetch execution files (`C:\Windows\Prefetch`).
   - **Memory & Kernel Dumps**: Cleans multi-gigabyte `C:\Windows\MEMORY.DMP` and `LiveKernelReports`.
   - **DNS Resolver Cache**: Flushes network cache via `ipconfig /flushdns`.
   - **Developer Super-Pack**: Cleans NPM package cache (`%LocalAppData%\npm-cache`), VS Code & Cursor caches, and Yarn cache.

3. **Interactive Tabbed Tool Suite**:
   - **Tab 1: 🚀 1-Click Optimizer**:
     - Dual-drive telemetry header
     - Scope switcher (`All Drives`, `Drive C:`, `Drive D:`)
     - Presets: `Safe Fast Clean`, `Deep System Clean`, `Drive D: Clean`, `Developer Clean`, `Select All`
     - Real-time terminal with live logs & space tally
   - **Tab 2: 🔍 Large Files Finder**:
     - Multi-drive scanning (Both Drives, Drive C:, Drive D:)
     - Configurable thresholds (`>= 50 MB`, `>= 100 MB`, `>= 250 MB`, `>= 500 MB`, `>= 1 GB`)
     - Open in Explorer & Delete Selected File actions
   - **Tab 3: 👥 Fast Duplicate Files Finder**:
     - High-performance 3-stage duplicate file detector (Size filter -> 4KB head hash -> full SHA-256)
     - Shows wasted space and duplicate file paths
     - Safe deletion of duplicate copies
   - **Tab 4: 🧹 Empty Folders Cleaner**:
     - Scans and safely removes orphan empty directory trees (protecting system folders)

4. **One-Click Desktop Access**:
   - Desktop Shortcut: `Disk Optimizer Pro - Kamran Ashraf.lnk`
   - Automated UAC elevation on launch so all administrative commands execute seamlessly without permission errors.

---

## How to Run

### Via Desktop Shortcut
Double-click the **Disk Optimizer Pro - Kamran Ashraf** shortcut on your Desktop.

### Via Command Line
```powershell
python "C:\Users\chkam\OneDrive\Desktop\DiskOptimizerPro\launcher.pyw"
```
Or for direct console launch:
```powershell
python "C:\Users\chkam\OneDrive\Desktop\DiskOptimizerPro\main.py"
```
