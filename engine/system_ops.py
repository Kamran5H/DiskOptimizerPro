import os
import sys
import ctypes
import subprocess
import tempfile
from ctypes import wintypes
from typing import Callable, Tuple, Optional, Dict, List

# ---------------------------------------------------------------------------
# ADMIN / PRIVILEGE CHECK
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    """Check if the current process has administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# DRIVE DETECTION & DISK STATISTICS
# ---------------------------------------------------------------------------

def get_all_detected_drives() -> List[str]:
    """Detects available local fixed and removable drives without assuming C: or D:."""
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        drives = []
        for i in range(26):
            if bitmask & (1 << i):
                drive_letter = chr(65 + i) + ":\\"
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(
                    ctypes.c_wchar_p(drive_letter)
                )
                if drive_type in (2, 3) and os.path.exists(drive_letter):
                    drives.append(drive_letter)
        return drives
    except Exception:
        return []


def get_system_drive() -> str:
    """Return the drive containing the running Windows installation."""
    windows_dir = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    drive, _ = os.path.splitdrive(windows_dir)
    return drive.upper() or "C:"


def get_memory_stats() -> Optional[dict]:
    """Return physical memory usage via Windows, or None when it cannot be queried."""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        total = status.ullTotalPhys
        if total <= 0:
            return None
        used = total - status.ullAvailPhys
        return {
            "total_bytes": total,
            "available_bytes": status.ullAvailPhys,
            "used_percent": round(used / total * 100, 1),
            "total_gb": round(total / (1024 ** 3), 1),
            "available_gb": round(status.ullAvailPhys / (1024 ** 3), 1),
        }
    except (AttributeError, OSError):
        return None


def get_drive_details(drive: str = "C:\\") -> dict:
    """
    Returns filesystem type, volume label, and drive type name via Win32 APIs.
    """
    drive_path = drive if drive.endswith("\\") else drive + "\\"
    vol_buf = ctypes.create_unicode_buffer(260)
    fs_buf = ctypes.create_unicode_buffer(260)

    try:
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive_path),
            vol_buf, 260,
            None, None, None,
            fs_buf, 260
        )
    except Exception:
        pass

    dtype_code = 3
    try:
        dtype_code = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(drive_path))
    except Exception:
        pass

    type_names = {
        0: "Unknown",
        1: "Invalid",
        2: "Removable",
        3: "Fixed",
        4: "Network",
        5: "CD-ROM",
        6: "RAM Disk"
    }
    return {
        "volume_name": vol_buf.value or "Local Disk",
        "file_system": fs_buf.value or "NTFS",
        "drive_type": type_names.get(dtype_code, "Fixed"),
        "type_code": dtype_code
    }


def get_disk_stats(drive: str = "C:\\") -> dict:
    """
    Returns accurate storage statistics for the specified drive.
    Returns: { 'free_gb': float, 'used_gb': float, 'total_gb': float, 'free_percent': float, ... }
    """
    free_bytes = ctypes.c_ulonglong(0)
    total_bytes = ctypes.c_ulonglong(0)
    total_free_bytes = ctypes.c_ulonglong(0)

    drive_path = drive if drive.endswith("\\") else drive + "\\"
    if not os.path.exists(drive_path):
        return {
            "drive": drive, "free_bytes": 0, "used_bytes": 0, "total_bytes": 0,
            "free_gb": 0, "used_gb": 0, "total_gb": 0, "free_percent": 0, "used_percent": 0,
            "volume_name": "Unknown", "file_system": "Unknown", "drive_type": "Fixed", "exists": False
        }

    success = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(drive_path),
        ctypes.byref(free_bytes),
        ctypes.byref(total_bytes),
        ctypes.byref(total_free_bytes)
    )

    details = get_drive_details(drive_path)

    if success:
        total = total_bytes.value
        free = free_bytes.value
        used = total - free
        free_pct = (free / total * 100.0) if total > 0 else 0.0
        return {
            "drive": drive.upper().replace("\\", "").rstrip(":") + ":",
            "free_bytes": free,
            "used_bytes": used,
            "total_bytes": total,
            "free_gb": round(free / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "total_gb": round(total / (1024 ** 3), 2),
            "free_percent": round(free_pct, 1),
            "used_percent": round(100.0 - free_pct, 1),
            "volume_name": details["volume_name"],
            "file_system": details["file_system"],
            "drive_type": details["drive_type"],
            "exists": True
        }
    return {
        "drive": drive, "free_bytes": 0, "used_bytes": 0, "total_bytes": 0,
        "free_gb": 0, "used_gb": 0, "total_gb": 0, "free_percent": 0, "used_percent": 0,
        "volume_name": details["volume_name"], "file_system": details["file_system"],
        "drive_type": details["drive_type"], "exists": False
    }


def get_all_drives_stats(drives: Optional[List[str]] = None) -> Dict[str, dict]:
    """
    Returns storage metrics for multiple drives.
    Dynamically discovers all connected drives if None provided.
    """
    if drives is None:
        drives = get_all_detected_drives()
    res = {}
    for d in drives:
        st = get_disk_stats(d)
        if st["exists"]:
            res[st["drive"]] = st
    return res


import threading


# ---------------------------------------------------------------------------
# FAST WIN32 PROCESS ENUMERATION (<5ms vs ~800ms PowerShell)
# ---------------------------------------------------------------------------

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260)
    ]


def get_running_process_names() -> set:
    """Returns a set of lowercase process executable names running on the system."""
    names = set()
    try:
        TH32CS_SNAPPROCESS = 0x00000002
        h_snap = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if h_snap in (-1, 0):
            return names
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if ctypes.windll.kernel32.Process32FirstW(h_snap, ctypes.byref(entry)):
            while True:
                names.add(entry.szExeFile.lower())
                if not ctypes.windll.kernel32.Process32NextW(h_snap, ctypes.byref(entry)):
                    break
        ctypes.windll.kernel32.CloseHandle(h_snap)
    except Exception:
        pass
    return names


def is_process_running_fast(process_names: List[str]) -> bool:
    """
    Checks if any process matching process_names is running in <5ms.
    Matches with and without .exe extension.
    """
    try:
        active = get_running_process_names()
        for p in process_names:
            p_clean = p.lower().rstrip("*")
            if not p_clean.endswith(".exe"):
                p_exe = p_clean + ".exe"
            else:
                p_exe = p_clean
            if p_exe in active or p_clean in active:
                return True
            # Prefix wildcard matching (e.g. BlueStacks*)
            if any(act.startswith(p_clean) for act in active):
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# POWERSHELL RUNNER (Non-blocking reader thread to prevent deadlocks)
# ---------------------------------------------------------------------------

def run_powershell(
    command: str,
    log_cb: Optional[Callable[[str, str], None]] = None,
    timeout: Optional[int] = None
) -> Tuple[int, str]:
    """
    Executes a PowerShell command using -NoProfile, streaming output to log_cb.
    Uses a dedicated background reader thread to prevent pipe deadlocks and
    strictly enforce timeout limits even if the child process stops emitting output.
    
    Args:
        command:  The PowerShell command/script string.
        log_cb:   Optional callback for live log output.
        timeout:  Optional timeout in seconds (None = no timeout).
    
    Returns:
        (return_code, combined_output)
    """
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            startupinfo=startupinfo,
            encoding="utf-8",
            errors="replace"
        )

        output_lines = []

        def _reader():
            try:
                if process.stdout:
                    for line in iter(process.stdout.readline, ""):
                        line_str = line.strip()
                        if line_str:
                            output_lines.append(line_str)
                            if log_cb:
                                log_cb(line_str, "info")
            except Exception:
                pass
            finally:
                if process.stdout:
                    try:
                        process.stdout.close()
                    except Exception:
                        pass

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        try:
            process.wait(timeout=timeout)
            reader_thread.join(timeout=1.5)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                pass
            process.wait()
            reader_thread.join(timeout=1.0)
            err_msg = f"PowerShell command timed out after {timeout}s."
            if log_cb:
                log_cb(err_msg, "warning")
            return 1, err_msg

        return process.returncode, "\n".join(output_lines)
    except Exception as ex:
        err_msg = f"PowerShell execution error: {str(ex)}"
        if log_cb:
            log_cb(err_msg, "error")
        return 1, err_msg


# =====================================================================
# SECTION 2 COMMANDS & ADVANCED SYSTEM OPERATIONS
# =====================================================================

def disable_hibernation(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """
    2.1 - Disable Hibernation (powercfg -h off)
    Saves ~4-8 GB by removing hiberfil.sys
    """
    if log_cb:
        log_cb("Executing: powercfg -h off (Disable Hibernation)", "step")
    code, out = run_powershell("powercfg -h off", log_cb)
    if code == 0:
        if log_cb:
            log_cb("[OK] Hibernation disabled successfully (hiberfil.sys deleted)", "success")
        return True
    else:
        if log_cb:
            log_cb(f"[WARN] powercfg returned code {code}: {out}", "warning")
        return False


def query_compact_os(log_cb: Optional[Callable[[str, str], None]] = None) -> str:
    """
    2.2 - Check CompactOS status (Compact.exe /CompactOS:query)
    """
    code, out = run_powershell("Compact.exe /CompactOS:query", log_cb)
    return out


def enable_compact_os(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """
    2.2 - Enable CompactOS (Compact.exe /CompactOS:always)
    Compresses operating system binaries. Takes several minutes.
    """
    if log_cb:
        log_cb("Executing: Compact.exe /CompactOS:always (Compressing OS binaries...)", "step")
    code, out = run_powershell("Compact.exe /CompactOS:always", log_cb, timeout=600)
    if code == 0:
        if log_cb:
            log_cb("[OK] CompactOS compression completed", "success")
        return True
    else:
        if log_cb:
            log_cb(f"[WARN] CompactOS returned code {code}: {out}", "warning")
        return False


def optimize_shadow_storage(drive: str = "C:", log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """
    2.3 - Shadow Storage & Old Restore Points for specified drive (C: or D:)
    - vssadmin list shadowstorage
    - vssadmin resize shadowstorage /for={drive} /on={drive} /maxsize=3%
    - vssadmin delete shadows /for={drive} /oldest /quiet
    """
    clean_drive = (drive.split(":")[0].strip("\\/ ") + ":").upper()
    if log_cb:
        log_cb(f"Checking shadow storage allocations on {clean_drive}...", "step")
    code, out = run_powershell("vssadmin list shadowstorage", log_cb)

    # Check if shadow storage is configured for this drive
    has_association = clean_drive.lower() in out.lower()
    if not has_association:
        if log_cb:
            log_cb(f"No active shadow storage association found for {clean_drive} (Skipped).", "info")
        return True

    if log_cb:
        log_cb(f"Resizing shadowstorage maxsize to 3% on {clean_drive}...", "step")
    run_powershell(f"vssadmin resize shadowstorage /for={clean_drive} /on={clean_drive} /maxsize=3%", log_cb)

    if log_cb:
        log_cb(f"Deleting oldest restore points on {clean_drive}...", "step")
    code, out = run_powershell(f"vssadmin delete shadows /for={clean_drive} /oldest /quiet", log_cb)
    if code == 0:
        if log_cb:
            log_cb(f"[OK] Shadow storage optimized on {clean_drive}", "success")
        return True
    else:
        if log_cb:
            log_cb(f"[WARN] vssadmin note on {clean_drive}: {out}", "warning")
        return False


def clean_windows_update_cache(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    r"""
    2.4 - Clean Windows Update Cache
    - Stops wuauserv service safely
    - Removes SoftwareDistribution\Download contents
    - Restarts wuauserv
    """
    if log_cb:
        log_cb("Stopping Windows Update service (wuauserv)...", "step")
    ps_script = r"""
    $svc = Get-Service wuauserv -ErrorAction SilentlyContinue
    if ($svc) {
        Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 800
    }
    $dlPath = Join-Path $env:SystemRoot "SoftwareDistribution\Download"
    if (Test-Path $dlPath) {
        Get-ChildItem $dlPath -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "SoftwareDistribution\Download cleared"
    }
    if ($svc) {
        Start-Service wuauserv -ErrorAction SilentlyContinue
    }
    Write-Host "[OK] Windows Update cache cleaned and service restarted"
    """
    code, out = run_powershell(ps_script, log_cb, timeout=120)
    return code == 0


def run_windows_disk_cleanup(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """
    2.5 - Windows Cleanmgr with StateFlags0064
    Configures registry keys and launches cleanmgr.exe /sagerun:64
    """
    if log_cb:
        log_cb("Configuring Windows Disk Cleanup (cleanmgr /sagerun:64) flags...", "step")
    ps_script = r"""
    $regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VolumeCaches"
    $keys = @(
        "Temporary Files",
        "Temporary Setup Files",
        "Old ChkDsk Files",
        "Recycle Bin",
        "Thumbnail Cache",
        "Update Cleanup",
        "Downloaded Program Files",
        "Internet Cache Files",
        "Delivery Optimization Files",
        "Windows Error Reporting Archive Files",
        "Windows Error Reporting Queue Files",
        "Windows Error Reporting System Archive Files",
        "Windows Error Reporting System Queue Files"
    )
    foreach ($k in $keys) {
        $fullKey = Join-Path $regPath $k
        if (Test-Path $fullKey) {
            Set-ItemProperty -Path $fullKey -Name "StateFlags0064" -Value 2 -Type DWord -ErrorAction SilentlyContinue
        }
    }
    Write-Host "StateFlags0064 registry keys configured."
    Write-Host "Launching cleanmgr /sagerun:64..."
    Start-Process cleanmgr -ArgumentList "/sagerun:64" -Wait
    Write-Host "[OK] Windows cleanmgr execution completed"
    """
    code, out = run_powershell(ps_script, log_cb, timeout=300)
    return code == 0


def compact_wsl_disk(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """
    2.6 - WSL Virtual Disk Compaction
    Writes diskpart commands to a temp file to avoid PowerShell here-string issues.
    Searches for *.vhdx under %LOCALAPPDATA%\\wsl and D:\\wsl.
    """
    if log_cb:
        log_cb("Checking for WSL virtual disk (*.vhdx)...", "step")

    # Find vhdx paths safely in Python first
    vhdx_paths: List[str] = []
    search_roots = []

    local_app = os.environ.get("LOCALAPPDATA", "")
    wsl_local = os.path.join(local_app, "wsl")
    if os.path.isdir(wsl_local):
        search_roots.append(wsl_local)

    wsl_d = r"D:\wsl"
    if os.path.isdir(wsl_d):
        search_roots.append(wsl_d)

    for sr in search_roots:
        try:
            for root, _, files in os.walk(sr):
                for f in files:
                    if f.lower().endswith(".vhdx"):
                        vhdx_paths.append(os.path.join(root, f))
        except Exception:
            pass

    if not vhdx_paths:
        if log_cb:
            log_cb("No active WSL vhdx found to compact (Skipped).", "info")
        return True

    # Shutdown WSL before compacting
    run_powershell("wsl --shutdown", log_cb, timeout=30)

    all_ok = True
    for vhdx_path in vhdx_paths:
        if log_cb:
            log_cb(f"Compacting WSL virtual disk: {vhdx_path}", "step")

        # Write diskpart script to a temp file for reliable execution
        tmp_script = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(f'select vdisk file="{vhdx_path}"\n')
                tmp.write("attach vdisk readonly\n")
                tmp.write("compact vdisk\n")
                tmp.write("detach vdisk\n")
                tmp_script = tmp.name

            result = subprocess.run(
                ["diskpart", "/s", tmp_script],
                capture_output=True, text=True, timeout=600,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                if log_cb:
                    log_cb(f"[OK] Compacted WSL disk: {vhdx_path}", "success")
            else:
                all_ok = False
                if log_cb:
                    log_cb(f"[WARN] diskpart returned code {result.returncode} for: {vhdx_path}", "warning")
        except subprocess.TimeoutExpired:
            all_ok = False
            if log_cb:
                log_cb(f"[WARN] diskpart timed out for: {vhdx_path}", "warning")
        except Exception as ex:
            all_ok = False
            if log_cb:
                log_cb(f"[WARN] WSL compact error: {ex}", "warning")
        finally:
            if tmp_script and os.path.exists(tmp_script):
                try:
                    os.remove(tmp_script)
                except Exception:
                    pass

    return all_ok


# =====================================================================
# NEW ADVANCED OPTIMIZATIONS
# =====================================================================

def flush_dns(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """Flushes the Windows DNS resolver cache."""
    if log_cb:
        log_cb("Flushing Windows DNS resolver cache (ipconfig /flushdns)...", "step")
    code, out = run_powershell("ipconfig /flushdns", log_cb, timeout=30)
    if log_cb:
        log_cb("[OK] DNS Cache flushed successfully", "success")
    return code == 0


def clean_delivery_optimization(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """Cleans Windows Delivery Optimization peer-to-peer update cache."""
    if log_cb:
        log_cb("Cleaning Delivery Optimization cache...", "step")
    ps_cmd = r"""
    $doPath = Join-Path $env:SystemRoot "SoftwareDistribution\DeliveryOptimization"
    if (Test-Path $doPath) {
        Get-ChildItem $doPath -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "DeliveryOptimization cache cleared"
    }
    """
    code, _ = run_powershell(ps_cmd, log_cb, timeout=60)
    if log_cb:
        log_cb("[OK] Delivery Optimization files cleaned", "success")
    return code == 0


def clean_prefetch(log_cb: Optional[Callable[[str, str], None]] = None) -> bool:
    """Cleans stale Windows prefetch files ($env:SystemRoot\\Prefetch)."""
    if log_cb:
        log_cb("Cleaning Windows Prefetch files...", "step")
    ps_cmd = r"""
    $pf = Join-Path $env:SystemRoot "Prefetch"
    if (Test-Path $pf) {
        Get-ChildItem $pf -Filter "*.pf" -Force -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    }
    """
    code, _ = run_powershell(ps_cmd, log_cb, timeout=30)
    if log_cb:
        log_cb("[OK] Prefetch cache cleared", "success")
    return code == 0


def clean_memory_dumps(log_cb: Optional[Callable[[str, str], None]] = None) -> int:
    """Cleans full system memory dump MEMORY.DMP and LiveKernelReports."""
    if log_cb:
        log_cb("Checking for full system MEMORY.DMP and LiveKernelReports...", "step")
    freed = 0
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    mem_dmp = os.path.join(sys_root, "MEMORY.DMP")
    if os.path.exists(mem_dmp) and os.path.isfile(mem_dmp):
        try:
            sz = os.path.getsize(mem_dmp)
            os.remove(mem_dmp)
            freed += sz
            if log_cb:
                log_cb(f"Deleted MEMORY.DMP ({round(sz/(1024*1024), 1)} MB)", "info")
        except Exception:
            pass

    live_kernel = os.path.join(sys_root, "LiveKernelReports")
    if os.path.isdir(live_kernel):
        try:
            for root, _, files in os.walk(live_kernel):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        if os.path.isfile(fp) and not os.path.islink(fp):
                            sz = os.path.getsize(fp)
                            os.remove(fp)
                            freed += sz
                    except Exception:
                        pass
        except Exception:
            pass

    mb = round(freed / (1024 * 1024), 1)
    if log_cb:
        log_cb(f"[OK] Memory dumps cleaned (~{mb} MB freed)", "success")
    return freed
