# 🚀 Disk Optimizer Pro V2

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Kamran5H/DiskOptimizerPro)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/Kamran5H/DiskOptimizerPro)
[![GUI](https://img.shields.io/badge/GUI-CustomTkinter%20Modern%20Dark-6366F1?style=for-the-badge)](https://github.com/Kamran5H/DiskOptimizerPro)
[![Safety](https://img.shields.io/badge/Safety-Kernel--Safe%20%7C%20Zero--Destruction-10B981?style=for-the-badge)](https://github.com/Kamran5H/DiskOptimizerPro)

**Executive dual-drive (C: & D:) Windows system cleanup, duplicate hunter, and disk optimization suite with a modern CustomTkinter GUI.**

[Features](#-features) • [Architecture](#-architecture) • [Safety Protocol](#-safety--whitelist-protocols) • [Installation](#-installation) • [License](#-license)

</div>

---

## 🌟 Executive Overview

**Disk Optimizer Pro V2** is a native Windows system optimization and disk hygiene suite built in Python with **CustomTkinter**. Designed specifically for power workstations with dual-drive configurations (System SSD `C:` and Secondary Storage `D:`), it provides a military-grade cleanup engine that safely reclaims tens of gigabytes of disk space while rigorously safeguarding essential operating system components, developer toolchains, and user credentials.

---

## 🚀 Features

- **💽 Dual-Drive Telemetry**: Real-time visual disk meter displaying capacity, used storage, and free space on both `C:` and `D:` partitions simultaneously.
- **🧹 Deep System Hygiene (`cleaner_engine.py`)**:
  - Windows Update residual files & Delivery Optimization caches
  - Crash dumps, error reports, and diagnostic memory snapshots
  - Temp directories (`%TEMP%`, `C:\Windows\Temp`)
  - Web browser caches (Chrome, Edge, Brave, Firefox)
  - Package manager caches (`pip`, `npm`, `yarn`, `cargo`)
- **👯 High-Speed Duplicate Hunter (`duplicate_finder.py`)**: Multi-threaded duplicate detection combining file size pre-filtering with chunked cryptographic hashing (SHA256) to identify redundant files without reading full disk contents into RAM.
- **📂 Recursive Empty Directory Pruner (`empty_folder_cleaner.py`)**: Safely purges abandoned, empty folder trees left behind by uninstalled software.
- **📊 Large File Space Analyzer (`large_files.py`)**: Scans and sorts files exceeding configurable size thresholds (e.g. >100MB / >1GB) for immediate manual review.
- **🎨 Modern CustomTkinter Dark Theme**: Sleek, high-contrast dark GUI with responsive progress animations, scan statistics, and selective confirmation toggles.

---

## 🛡️ Safety & Whitelist Protocols

Disk Optimizer Pro enforces non-negotiable safety guardrails to ensure system stability:
- **Zero OS Destruction**: System-critical directories (`System32`, `WinSxS`, `Boot`, driver stores) are permanently hardcoded into immutable exclusion lists.
- **Developer Safety**: Preserves active Git repositories (`.git/`), IDE settings (`.vscode`, `.idea`), and active virtual environments.
- **Lock Detection**: Skips files actively locked by running Windows processes without crashing.
- **Recycle Bin Routing**: Optional safe-delete mode moves files to the Windows Recycle Bin rather than permanently unlinking them.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    A[CustomTkinter GUI Bridge: gui/] --> B[System Telemetry: system_ops.py]
    B --> C{Optimization Engine}
    
    subgraph Core Modules [engine/]
        C --> D[cleaner_engine.py: Temp / Logs / Caches]
        C --> E[duplicate_finder.py: SHA256 Chunked Hashing]
        C --> F[empty_folder_cleaner.py: Recursive Tree Pruner]
        C --> G[large_files.py: Space Hog Inspector]
    end
    
    Core Modules --> H[Safety Validator & Whitelist Filter]
    H --> I{Execute Action}
    I -->|Safe Deletion| J[(Recycle Bin / Reclaimed Space)]
```

---

## 📁 Repository Structure

```text
DiskOptimizerPro/
├── main.py                     # Primary GUI application entry point
├── launcher.pyw                # Windowless background launcher
├── create_shortcut.py          # Desktop shortcut installer script
├── engine/                     # Core backend execution modules
│   ├── cleaner_engine.py       # Temporary files, caches, and logs cleanup logic
│   ├── duplicate_finder.py     # Fast cryptographic duplicate file detector
│   ├── empty_folder_cleaner.py # Tree-walking empty folder pruner
│   ├── large_files.py          # Heavy storage consumer scanner
│   └── system_ops.py           # Drive space calculation & Windows shell APIs
├── gui/                        # CustomTkinter interface components & styling
├── assets/                     # Icons, logos, and UI graphics
├── tests/                      # Automated safety and engine test suites
├── .gitignore                  # Python & Windows build artifact exclusions
└── LICENSE                     # Open-source MIT License
```

---

## ⚡ Installation

### Prerequisites
- Windows 10 or 11
- Python 3.10 or higher

### Setup
```bash
git clone https://github.com/Kamran5H/DiskOptimizerPro.git
cd DiskOptimizerPro

# Setup virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install requirements
pip install customtkinter psutil send2trash
```

### Launch
```bash
# Launch interactive GUI
python main.py

# Or create a Desktop Shortcut:
python create_shortcut.py
```

---

## 📜 License

This project is open-source and released under the [MIT License](LICENSE).  
Copyright (c) 2024-2026 **Kamran Ashraf**.
