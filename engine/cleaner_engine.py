import os
import re
import shutil
from typing import Callable, Dict, List, Optional, Tuple

from engine.system_ops import (
    get_disk_stats,
    get_all_drives_stats,
    run_powershell,
    disable_hibernation,
    enable_compact_os,
    optimize_shadow_storage,
    clean_windows_update_cache,
    run_windows_disk_cleanup,
    compact_wsl_disk,
    flush_dns,
    clean_delivery_optimization,
    clean_prefetch,
    clean_memory_dumps
)


# ---------------------------------------------------------------------------
# SAFE FOLDER CONTENT DELETER
# ---------------------------------------------------------------------------

def delete_folder_contents(
    folder_path: str,
    log_cb: Optional[Callable[[str, str], None]] = None
) -> int:
    """
    Deletes all files and subdirectories inside folder_path.
    - Skips symbolic links to prevent following dangerous targets.
    - Clears read-only flags before deletion.
    Returns total bytes freed.
    """
    if not folder_path or not os.path.isdir(folder_path):
        return 0

    def _remove_readonly(func, path, exc_info):
        try:
            os.chmod(path, 0o777)
            func(path)
        except Exception:
            pass

    total_freed = 0
    try:
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            try:
                if os.path.islink(item_path):
                    # Skip symlinks — never follow them
                    continue
                if os.path.isfile(item_path):
                    size = 0
                    try:
                        size = os.path.getsize(item_path)
                    except OSError:
                        pass
                    try:
                        os.chmod(item_path, 0o777)
                        os.remove(item_path)
                        total_freed += size
                    except Exception:
                        pass
                elif os.path.isdir(item_path):
                    # Measure first, then delete
                    for root, _, files in os.walk(item_path, followlinks=False):
                        for f in files:
                            try:
                                total_freed += os.path.getsize(os.path.join(root, f))
                            except Exception:
                                pass
                    shutil.rmtree(item_path, onerror=_remove_readonly)
            except Exception:
                continue
    except Exception:
        pass
    return total_freed


# ---------------------------------------------------------------------------
# PROCESS HELPERS
# ---------------------------------------------------------------------------

def is_process_running(process_names: List[str]) -> bool:
    """Checks whether any process matching the given names is running."""
    try:
        names_str = ",".join(f'"{p}"' for p in process_names)
        cmd = (
            f"Get-Process -Name {names_str} -ErrorAction SilentlyContinue "
            "| Select-Object -ExpandProperty Name"
        )
        code, out = run_powershell(cmd, timeout=15)
        return bool(out.strip())
    except Exception:
        return False


def stop_processes(
    process_names: List[str],
    log_cb: Optional[Callable[[str, str], None]] = None
) -> None:
    """Force stops processes matching the given names."""
    if log_cb:
        log_cb(f"Stopping processes: {', '.join(process_names)}...", "info")
    names_str = ",".join(f'"{p}"' for p in process_names)
    cmd = (
        f"Get-Process -Name {names_str} -ErrorAction SilentlyContinue "
        "| Stop-Process -Force -ErrorAction SilentlyContinue"
    )
    run_powershell(cmd, log_cb, timeout=20)


# ---------------------------------------------------------------------------
# CLEANER ENGINE
# ---------------------------------------------------------------------------

class CleanerEngine:
    """
    Enhanced V2 cleanup engine supporting Drive C: and Drive D:
    plus advanced Windows & Developer optimization modules.
    """

    def __init__(self, log_cb: Optional[Callable[[str, str], None]] = None):
        self.log_cb = log_cb or (lambda msg, lvl: None)
        self.should_stop = False

    def log(self, message: str, level: str = "info"):
        self.log_cb(message, level)

    def cancel(self):
        """Signal the engine to stop at the next checkpoint."""
        self.should_stop = True

    def reset(self):
        """Reset the cancellation flag before a new run."""
        self.should_stop = False

    def _check_cancel(self) -> bool:
        """Returns True if cancellation was requested."""
        return self.should_stop

    # -----------------------------------------------------------------
    # SECTION 1: SYSTEM & TEMP CACHES
    # -----------------------------------------------------------------

    def clean_user_temp(self) -> int:
        """1.2 - User Temp ($env:TEMP)"""
        temp_dir = os.environ.get("TEMP", "")
        self.log(f"Cleaning User Temp ({temp_dir})...", "step")
        freed = delete_folder_contents(temp_dir, self.log_cb)
        self.log(f"[OK] User Temp cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_windows_temp(self) -> int:
        """1.3 - Windows Temp ($env:SystemRoot\\Temp)"""
        win_temp = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")
        self.log(f"Cleaning Windows Temp ({win_temp})...", "step")
        freed = delete_folder_contents(win_temp, self.log_cb)
        self.log(f"[OK] Windows Temp cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_error_reports(self) -> int:
        """1.4 - Windows Error Reporting (%ProgramData%\\Microsoft\\Windows\\WER)"""
        wer_dir = os.path.join(
            os.environ.get("ProgramData", r"C:\ProgramData"),
            "Microsoft", "Windows", "WER"
        )
        self.log(f"Cleaning Windows Error Reports ({wer_dir})...", "step")
        freed = delete_folder_contents(wer_dir, self.log_cb)
        self.log(f"[OK] Error Reports cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_thumbnail_cache(self) -> int:
        """1.5 - Thumbnail Cache ($env:LOCALAPPDATA\\Microsoft\\Windows\\Explorer\\thumbcache_*)"""
        local_app = os.environ.get("LOCALAPPDATA", "")
        exp_dir = os.path.join(local_app, "Microsoft", "Windows", "Explorer")
        self.log("Cleaning Thumbnail Cache (thumbcache_*)...", "step")
        freed = 0
        if os.path.isdir(exp_dir):
            for f in os.listdir(exp_dir):
                if f.lower().startswith("thumbcache_"):
                    p = os.path.join(exp_dir, f)
                    if os.path.isfile(p) and not os.path.islink(p):
                        try:
                            sz = os.path.getsize(p)
                            os.chmod(p, 0o777)
                            os.remove(p)
                            freed += sz
                        except Exception:
                            pass
        self.log(f"[OK] Thumbnail cache cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_recent_items(self) -> int:
        """1.6 - Recent Items ($env:APPDATA\\Microsoft\\Windows\\Recent)"""
        recent_dir = os.path.join(
            os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Recent"
        )
        self.log("Cleaning Recent Items shortcuts...", "step")
        freed = delete_folder_contents(recent_dir, self.log_cb)
        self.log("[OK] Recent items cleaned", "success")
        return freed

    def clean_recycle_bin(self, target_drives: Optional[List[str]] = None) -> int:
        """1.7 - Empty Windows Recycle Bin across specified drives"""
        drives_str = ", ".join(target_drives) if target_drives else "All Drives"
        self.log(f"Emptying Recycle Bin ({drives_str})...", "step")
        if target_drives and len(target_drives) == 1:
            letter = target_drives[0].replace(":", "").replace("\\", "").strip().upper()
            cmd = f"Clear-RecycleBin -DriveLetter {letter} -Force -ErrorAction SilentlyContinue"
        else:
            cmd = "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"
        run_powershell(cmd, self.log_cb, timeout=30)
        self.log(f"[OK] Recycle Bin emptied ({drives_str})", "success")
        return 0

    def clean_crash_dumps(self) -> int:
        """1.8 - Crash Dumps ($env:LOCALAPPDATA\\CrashDumps + $env:SystemRoot\\Minidump)"""
        self.log("Cleaning Crash Dumps & Minidumps...", "step")
        dump_paths = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "CrashDumps"),
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Minidump"),
        ]
        freed = 0
        for p in dump_paths:
            if os.path.isdir(p):
                freed += delete_folder_contents(p, self.log_cb)
                self.log(f"Cleaned dumps: {p}", "info")
        self.log(f"[OK] Crash dumps cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_font_d3ds_icon_cache(self) -> int:
        """1.9 - Font / D3DS / Icon Cache"""
        local_app = os.environ.get("LOCALAPPDATA", "")
        self.log("Cleaning FontCache, D3DSCache, and IconCache...", "step")
        freed = 0

        for cache_dir in ["FontCache", "D3DSCache"]:
            p = os.path.join(local_app, cache_dir)
            if os.path.isdir(p):
                freed += delete_folder_contents(p, self.log_cb)

        icon_db = os.path.join(local_app, "IconCache.db")
        if os.path.isfile(icon_db) and not os.path.islink(icon_db):
            try:
                freed += os.path.getsize(icon_db)
                os.chmod(icon_db, 0o777)
                os.remove(icon_db)
            except Exception:
                pass

        self.log(f"[OK] Font/D3DS/Icon cache cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    # -----------------------------------------------------------------
    # DRIVE D: DEDICATED CLEANERS
    # -----------------------------------------------------------------

    def clean_drive_d_root_junk(self) -> int:
        """
        Cleans Visual C++ installer leftovers and crash temp files in D:\\ root:
        eula.*.txt, install.exe, install.ini, install.res.*.dll, vcredist.bmp,
        VC_RED.cab, VC_RED.MSI, globdata.ini, DumpStack.log.tmp
        """
        d_root = "D:\\"
        if not os.path.isdir(d_root):
            self.log("Drive D: not found (Skipped).", "info")
            return 0

        self.log("Scanning Drive D: root for installer leftovers...", "step")
        junk_prefixes = ("eula.", "install.res.", "vc_red.")
        exact_junk = {
            "install.exe", "install.ini", "vcredist.bmp", "vc_red.cab",
            "vc_red.msi", "globdata.ini", "dumpstack.log.tmp"
        }

        freed = 0
        deleted_count = 0
        try:
            for item in os.listdir(d_root):
                item_lower = item.lower()
                is_junk = (
                    item_lower in exact_junk or
                    any(item_lower.startswith(pref) for pref in junk_prefixes)
                )
                if is_junk:
                    full_p = os.path.join(d_root, item)
                    if os.path.isfile(full_p) and not os.path.islink(full_p):
                        try:
                            sz = os.path.getsize(full_p)
                            os.chmod(full_p, 0o777)
                            os.remove(full_p)
                            freed += sz
                            deleted_count += 1
                            self.log(f"  Removed D: root junk: {item}", "info")
                        except Exception:
                            pass
        except Exception as ex:
            self.log(f"Drive D: scan note: {ex}", "warning")

        self.log(f"[OK] Drive D: root cleaned ({deleted_count} files, ~{round(freed/(1024*1024),2)} MB freed)", "success")
        return freed

    def clean_drive_d_python_caches(self) -> int:
        """Cleans __pycache__ and .pytest_cache directories across Drive D:\\"""
        d_root = "D:\\"
        if not os.path.isdir(d_root):
            return 0

        self.log("Sweeping Drive D: for __pycache__ and .pytest_cache folders...", "step")
        freed = 0
        folder_count = 0
        skip_dirs = {"$recycle.bin", "system volume information", "recovery"}
        target_cache_names = {"__pycache__", ".pytest_cache"}

        for root, dirs, _ in os.walk(d_root, topdown=True, followlinks=False):
            if self._check_cancel():
                break
            dirs[:] = [
                d for d in dirs
                if d.lower() not in skip_dirs and not d.startswith("$")
            ]
            for d in list(dirs):
                if d in target_cache_names:
                    target_p = os.path.join(root, d)
                    try:
                        for r, _, fs in os.walk(target_p, followlinks=False):
                            for f in fs:
                                try:
                                    freed += os.path.getsize(os.path.join(r, f))
                                except Exception:
                                    pass
                        shutil.rmtree(target_p, ignore_errors=True)
                        folder_count += 1
                        dirs.remove(d)
                    except Exception:
                        pass

        self.log(f"[OK] Drive D: developer caches cleaned ({folder_count} folders, ~{round(freed/(1024*1024),2)} MB freed)", "success")
        return freed

    # -----------------------------------------------------------------
    # BROWSER & DEVELOPER CACHES
    # -----------------------------------------------------------------

    def clean_chrome_caches(self) -> int:
        """1.10 - Chrome caches across ALL profiles"""
        local_app = os.environ.get("LOCALAPPDATA", "")
        chrome_base = os.path.join(local_app, "Google", "Chrome", "User Data")
        if not os.path.isdir(chrome_base):
            self.log("Chrome data not found (Skipping Chrome cache).", "info")
            return 0

        self.log(f"Cleaning Google Chrome caches ({chrome_base})...", "step")
        target_subdirs = [
            "Cache",
            "Code Cache",
            os.path.join("Service Worker", "CacheStorage"),
            "GPUCache",
            "DawnCache"
        ]

        freed = 0
        try:
            for entry in os.listdir(chrome_base):
                if re.match(r"^(Default|Profile)", entry, re.IGNORECASE):
                    prof_dir = os.path.join(chrome_base, entry)
                    if os.path.isdir(prof_dir):
                        for sub in target_subdirs:
                            target_p = os.path.join(prof_dir, sub)
                            if os.path.isdir(target_p):
                                freed += delete_folder_contents(target_p, self.log_cb)
                        self.log(f"Cleaned Chrome profile: {entry}", "info")

            shader_p = os.path.join(chrome_base, "ShaderCache")
            if os.path.isdir(shader_p):
                freed += delete_folder_contents(shader_p, self.log_cb)
        except Exception as ex:
            self.log(f"Chrome cleanup note: {ex}", "warning")

        self.log(f"[OK] Chrome caches cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_edge_caches(self) -> int:
        """1.11 - Edge caches across ALL profiles"""
        local_app = os.environ.get("LOCALAPPDATA", "")
        edge_base = os.path.join(local_app, "Microsoft", "Edge", "User Data")
        if not os.path.isdir(edge_base):
            self.log("Edge data not found (Skipping Edge cache).", "info")
            return 0

        self.log(f"Cleaning Microsoft Edge caches ({edge_base})...", "step")
        target_subdirs = [
            "Cache",
            "Code Cache",
            os.path.join("Service Worker", "CacheStorage"),
            "GPUCache"
        ]

        freed = 0
        try:
            for entry in os.listdir(edge_base):
                if re.match(r"^(Default|Profile)", entry, re.IGNORECASE):
                    prof_dir = os.path.join(edge_base, entry)
                    if os.path.isdir(prof_dir):
                        for sub in target_subdirs:
                            target_p = os.path.join(prof_dir, sub)
                            if os.path.isdir(target_p):
                                freed += delete_folder_contents(target_p, self.log_cb)
                        self.log(f"Cleaned Edge profile: {entry}", "info")
        except Exception as ex:
            self.log(f"Edge cleanup note: {ex}", "warning")

        self.log(f"[OK] Edge caches cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_pip_cache(self) -> int:
        """1.12 - pip cache ($env:LOCALAPPDATA\\pip\\cache)"""
        pip_cache = os.path.join(os.environ.get("LOCALAPPDATA", ""), "pip", "cache")
        self.log("Cleaning Python pip package cache...", "step")
        freed = delete_folder_contents(pip_cache, self.log_cb)
        self.log(f"[OK] pip cache cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_bloated_chrome_history(self) -> int:
        """1.13 - Bloated Chrome History & Favicons (> 10MB)"""
        local_app = os.environ.get("LOCALAPPDATA", "")
        chrome_base = os.path.join(local_app, "Google", "Chrome", "User Data")
        if not os.path.isdir(chrome_base):
            return 0

        self.log("Checking Chrome History & Favicons (> 10MB threshold)...", "step")
        freed = 0
        limit_bytes = 10 * 1024 * 1024

        try:
            for entry in os.listdir(chrome_base):
                if re.match(r"^(Default|Profile)", entry, re.IGNORECASE):
                    prof_dir = os.path.join(chrome_base, entry)
                    if os.path.isdir(prof_dir):
                        for file_name in ["History", "Favicons"]:
                            file_path = os.path.join(prof_dir, file_name)
                            if os.path.isfile(file_path) and not os.path.islink(file_path):
                                sz = os.path.getsize(file_path)
                                if sz > limit_bytes:
                                    try:
                                        os.remove(file_path)
                                        freed += sz
                                        self.log(f"[OK] Deleted bloated {entry}\\{file_name} ({round(sz/(1024*1024),1)} MB)", "info")
                                    except Exception:
                                        pass
        except Exception as ex:
            self.log(f"Chrome history check: {ex}", "warning")

        self.log(f"[OK] Chrome history check complete (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_old_playwright_versions(self) -> int:
        """1.14 - Old Playwright browser versions ($env:LOCALAPPDATA\\ms-playwright)"""
        pw_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
        if not os.path.isdir(pw_dir):
            self.log("Playwright directory not found (Skipped).", "info")
            return 0

        self.log(f"Scanning old Playwright builds ({pw_dir})...", "step")
        browser_prefixes = ["chromium-", "chromium_headless_shell-", "firefox-", "webkit-"]
        freed = 0

        def _remove_ro(func, path, exc):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass

        try:
            all_dirs = [
                d for d in os.listdir(pw_dir)
                if os.path.isdir(os.path.join(pw_dir, d))
            ]
            for prefix in browser_prefixes:
                matches = sorted(
                    [d for d in all_dirs if d.startswith(prefix)],
                    # FIXED: numerical sort so build 1097 > 998 correctly
                    key=lambda s: [int(x) for x in re.findall(r"\d+", s)] or [0]
                )
                if len(matches) > 1:
                    for old_v in matches[:-1]:   # keep only the newest
                        p = os.path.join(pw_dir, old_v)
                        self.log(f"Removing old Playwright build: {old_v}", "info")
                        for root, _, files in os.walk(p, followlinks=False):
                            for f in files:
                                try:
                                    freed += os.path.getsize(os.path.join(root, f))
                                except Exception:
                                    pass
                        shutil.rmtree(p, onerror=_remove_ro)
                        self.log(f"[OK] Removed old: {old_v}", "success")
        except Exception as ex:
            self.log(f"Playwright cleanup note: {ex}", "warning")

        self.log(f"[OK] Playwright cleanup completed (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_old_opera_versions(self) -> int:
        """1.15 - Old Opera versions ($env:LOCALAPPDATA\\Programs\\Opera)"""
        opera_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Opera")
        if not os.path.isdir(opera_dir):
            self.log("Opera directory not found (Skipped).", "info")
            return 0

        self.log(f"Scanning old Opera version folders ({opera_dir})...", "step")
        freed = 0

        def _remove_ro(func, path, exc):
            try:
                os.chmod(path, 0o777)
                func(path)
            except Exception:
                pass

        try:
            dirs = [
                d for d in os.listdir(opera_dir)
                if os.path.isdir(os.path.join(opera_dir, d))
            ]
            # FIXED: numerical sort — 102.x correctly beats 99.x
            version_dirs = sorted(
                [d for d in dirs if re.match(r"^\d+\.", d)],
                key=lambda v: [int(x) for x in re.findall(r"\d+", v)] or [0]
            )
            if len(version_dirs) > 1:
                for old_v in version_dirs[:-1]:   # keep only the newest
                    p = os.path.join(opera_dir, old_v)
                    self.log(f"Removing old Opera version: {old_v}", "info")
                    for root, _, files in os.walk(p, followlinks=False):
                        for f in files:
                            try:
                                freed += os.path.getsize(os.path.join(root, f))
                            except Exception:
                                pass
                    shutil.rmtree(p, onerror=_remove_ro)
                    self.log(f"[OK] Removed old Opera: {old_v}", "success")
        except Exception as ex:
            self.log(f"Opera cleanup note: {ex}", "warning")

        self.log(f"[OK] Opera versions cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    def clean_mendeley_installer(self) -> int:
        """1.16 - Mendeley updater installer executable"""
        local_app = os.environ.get("LOCALAPPDATA", "")
        mendeley_exe = os.path.join(
            local_app,
            "@mendeley-internaldesktop-reference-manager-updater",
            "installer.exe"
        )
        freed = 0
        if os.path.isfile(mendeley_exe) and not os.path.islink(mendeley_exe):
            try:
                sz = os.path.getsize(mendeley_exe)
                os.chmod(mendeley_exe, 0o777)
                os.remove(mendeley_exe)
                freed += sz
                self.log(f"[OK] Mendeley updater installer removed ({round(sz/(1024*1024),1)} MB)", "success")
            except Exception as ex:
                self.log(f"Mendeley removal note: {ex}", "warning")
        else:
            self.log("Mendeley installer not found (Skipped).", "info")
        return freed

    def clean_bluestacks(self) -> int:
        """
        1.17 - BlueStacks cleanup (Destructive — terminates and deletes files)
        WARNING: Only run if BlueStacks is not needed.
        """
        self.log("Terminating BlueStacks processes...", "step")
        stop_processes(["BlueStacks*", "BstkSVC*", "HD-Player*"], self.log_cb)

        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        local_app = os.environ.get("LOCALAPPDATA", "")
        bs_paths = [
            os.path.join(program_data, "BlueStacks_nxt"),
            os.path.join(local_app, "Bluestacks"),
            r"C:\Program Files\BlueStacks_nxt",
            r"C:\Program Files (x86)\BlueStacks_nxt",
            r"D:\BlueStacks_nxt",
            r"D:\Program Files\BlueStacks_nxt",
        ]

        freed = 0
        for p in bs_paths:
            if os.path.isdir(p):
                self.log(f"Removing BlueStacks folder: {p}...", "step")
                for root, _, files in os.walk(p, followlinks=False):
                    for f in files:
                        try:
                            freed += os.path.getsize(os.path.join(root, f))
                        except Exception:
                            pass
                shutil.rmtree(p, ignore_errors=True)
                self.log(f"[OK] Deleted: {p}", "success")

        self.log(f"[OK] BlueStacks cleanup completed (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    # -----------------------------------------------------------------
    # DEVELOPER CACHES SUPER-PACK
    # -----------------------------------------------------------------

    def clean_developer_caches(self) -> int:
        """Cleans NPM Cache, VS Code / Cursor caches, and Yarn cache."""
        self.log("Cleaning developer caches (NPM, VS Code, Cursor, Yarn)...", "step")
        freed = 0
        local_app = os.environ.get("LOCALAPPDATA", "")
        app_data = os.environ.get("APPDATA", "")

        # NPM cache
        npm_c = os.path.join(local_app, "npm-cache")
        if os.path.isdir(npm_c):
            freed += delete_folder_contents(npm_c, self.log_cb)

        # VS Code / Cursor caches
        vscode_dirs = [
            os.path.join(app_data, "Code", "Cache"),
            os.path.join(app_data, "Code", "CachedData"),
            os.path.join(app_data, "Code", "Service Worker", "CacheStorage"),
            os.path.join(app_data, "Cursor", "Cache"),
            os.path.join(app_data, "Cursor", "CachedData"),
        ]
        for vsc in vscode_dirs:
            if os.path.isdir(vsc):
                freed += delete_folder_contents(vsc, self.log_cb)

        # Yarn Cache
        yarn_c = os.path.join(local_app, "Yarn", "Cache")
        if os.path.isdir(yarn_c):
            freed += delete_folder_contents(yarn_c, self.log_cb)

        self.log(f"[OK] Developer caches cleaned (~{round(freed/(1024*1024),1)} MB freed)", "success")
        return freed

    # -----------------------------------------------------------------
    # SECTION 2: ADMINISTRATOR COMMANDS & ADVANCED OPTIMIZATIONS
    # -----------------------------------------------------------------

    def run_disable_hibernation(self) -> int:
        """2.1 - Disable Hibernation"""
        disable_hibernation(self.log_cb)
        return 0

    def run_compact_os(self) -> int:
        """2.2 - CompactOS compression"""
        enable_compact_os(self.log_cb)
        return 0

    def run_shadow_storage(self, drive: str = "C:") -> int:
        """2.3 - Optimize Shadow Storage for the given drive"""
        optimize_shadow_storage(drive, self.log_cb)
        return 0

    def run_shadow_storage_all(self) -> int:
        """Optimizes shadow storage on both C: and D:"""
        optimize_shadow_storage("C:", self.log_cb)
        if os.path.isdir("D:\\"):
            optimize_shadow_storage("D:", self.log_cb)
        return 0

    def run_windows_update(self) -> int:
        """2.4 - Windows Update Cache"""
        clean_windows_update_cache(self.log_cb)
        return 0

    def run_cleanmgr(self) -> int:
        """2.5 - Windows Disk Cleanup (cleanmgr /sagerun:64)"""
        run_windows_disk_cleanup(self.log_cb)
        return 0

    def run_wsl_compact(self) -> int:
        """2.6 - WSL Virtual Disk Compaction"""
        compact_wsl_disk(self.log_cb)
        return 0

    def run_flush_dns(self) -> int:
        """Flushes DNS Resolver cache"""
        flush_dns(self.log_cb)
        return 0

    def run_delivery_optimization(self) -> int:
        """Cleans Delivery Optimization files"""
        clean_delivery_optimization(self.log_cb)
        return 0

    def run_prefetch(self) -> int:
        """Cleans Windows Prefetch"""
        clean_prefetch(self.log_cb)
        return 0

    def run_memory_dumps(self) -> int:
        """Cleans MEMORY.DMP and LiveKernelReports"""
        return clean_memory_dumps(self.log_cb)
