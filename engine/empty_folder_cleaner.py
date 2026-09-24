import os
from typing import List, Callable, Optional, Tuple


# Protected system directory names (case-insensitive set)
SYSTEM_DIR_NAMES: set = {
    "$recycle.bin", "system volume information", "recovery",
    "config.msi", "msocache", "windowsapps"
}

# Version-control repository roots — never delete anything inside these
VCS_DIR_NAMES: set = {".git", ".svn", ".hg", ".bzr"}


def is_protected(path: str, base_root: str) -> bool:
    """
    Returns True when *path* must not be deleted.
    Protections:
      - The scanned root itself or any drive root
      - Windows system root tree  ($env:SystemRoot)
      - Program Files directories
      - System-named directories  (SYSTEM_DIR_NAMES)
      - VCS repository directories (VCS_DIR_NAMES)
      - AppData unless the path is inside %TEMP%
    """
    norm_path = os.path.normpath(path).lower()
    norm_root = os.path.normpath(base_root).lower()

    # Never delete the scanned root itself or a drive root
    drive, tail = os.path.splitdrive(path)
    if norm_path == norm_root or tail in ("\\", "/", ""):
        return True

    # Windows OS System Root
    sys_root = os.path.normpath(
        os.environ.get("SystemRoot", r"C:\Windows")
    ).lower()
    if norm_path == sys_root or norm_path.startswith(sys_root + os.sep):
        return True

    # Program Files
    prog_files = os.path.normpath(
        os.environ.get("ProgramFiles", r"C:\Program Files")
    ).lower()
    prog_files_x86 = os.path.normpath(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    ).lower()
    if norm_path == prog_files or norm_path.startswith(prog_files + os.sep):
        return True
    if prog_files_x86 and (norm_path == prog_files_x86 or norm_path.startswith(prog_files_x86 + os.sep)):
        return True

    parts = set(norm_path.split(os.sep))

    # System directories
    if parts.intersection(SYSTEM_DIR_NAMES):
        return True

    # VCS repositories — any parent component matches
    if parts.intersection(VCS_DIR_NAMES):
        return True

    # AppData — allow only if explicitly inside %TEMP%
    user_temp = os.environ.get("TEMP", "")
    if "appdata" in parts:
        norm_temp = os.path.normpath(user_temp).lower() if user_temp else ""
        if not (norm_temp and norm_path.startswith(norm_temp)):
            return True

    return False


def scan_empty_directories(
    roots: List[str],
    log_cb: Optional[Callable[[str, str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> List[str]:
    """
    Bottom-up scan to find orphan directories containing no files or subdirectories.
    Safely bypasses Windows system directories, VCS repos, and symlinks.

    Returns list of empty directory paths (deepest first, ready for deletion).
    """
    empty_dirs: List[str] = []

    for root_dir in roots:
        if not os.path.isdir(root_dir):
            continue

        if log_cb:
            log_cb(f"Scanning {root_dir} for empty directories...", "step")

        # topdown=False gives us bottom-up traversal — children before parents
        for current_dir, subdirs, files in os.walk(
            root_dir, topdown=False, followlinks=False
        ):
            if stop_check and stop_check():
                if log_cb:
                    log_cb("Scan cancelled by user.", "warning")
                return empty_dirs

            if is_protected(current_dir, root_dir):
                continue

            # Skip symlinks that look like directories
            if os.path.islink(current_dir):
                continue

            try:
                if not os.listdir(current_dir):
                    empty_dirs.append(current_dir)
            except (OSError, PermissionError):
                continue

    if log_cb:
        log_cb(
            f"Empty folder scan complete. Found {len(empty_dirs)} orphan empty folders.",
            "success"
        )

    return empty_dirs


def delete_empty_directories(
    dir_paths: List[str],
    log_cb: Optional[Callable[[str, str], None]] = None
) -> Tuple[int, int]:
    """
    Deletes the specified empty directories in bottom-up order
    (deepest paths first so parents can be removed after children).

    Returns (success_count, fail_count).
    """
    success = 0
    fail = 0

    # Sort deepest (longest path) first for safe bottom-up deletion
    sorted_paths = sorted(dir_paths, key=len, reverse=True)

    for p in sorted_paths:
        try:
            # Double-check it is still empty and not a symlink
            if os.path.islink(p):
                fail += 1
                continue
            if os.path.isdir(p) and not os.listdir(p):
                try:
                    os.chmod(p, 0o777)
                except Exception:
                    pass
                os.rmdir(p)
                success += 1
        except PermissionError:
            fail += 1
        except OSError:
            fail += 1

    if log_cb:
        log_cb(
            f"Cleaned {success} empty directories ({fail} skipped/locked).",
            "success"
        )

    return success, fail
