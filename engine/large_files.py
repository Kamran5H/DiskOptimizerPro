import os
from typing import List, Dict, Callable, Optional


def scan_large_files_multi(
    roots: Optional[List[str]] = None,
    min_size_mb: float = 50.0,
    top_n: int = 50,
    log_cb: Optional[Callable[[str, str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> List[Dict]:
    """
    High-speed recursive scanner for large files across multiple drives.
    Safely bypasses permission errors, symlinks, and system directories.

    Args:
        roots:       List of root paths to scan (defaults to all detected drives).
        min_size_mb: Minimum file size in MB to include.
        top_n:       Maximum number of results to return (sorted largest first).
        log_cb:      Optional progress/log callback(message, level).
        stop_check:  Optional callable that returns True when the scan should stop.

    Returns:
        List of dicts: {name, drive, path, size_bytes, size_mb, size_gb, ext}
    """
    if roots is None:
        # Fall back to C:\ if no roots given; D:\ added only if it exists
        from engine.system_ops import get_all_detected_drives
        roots = get_all_detected_drives()

    min_bytes = int(min_size_mb * 1024 * 1024)
    found_files: List[Dict] = []
    scanned_dirs = 0

    skip_dirs = {
        "$recycle.bin", "system volume information", "recovery", "config.msi",
        "msocache", "documents and settings"
    }

    if log_cb:
        log_cb(
            f"Starting deep scan on {', '.join(roots)} for files >= {min_size_mb} MB...",
            "step"
        )

    for root in roots:
        if not os.path.isdir(root):
            continue

        for dirpath, dirnames, filenames in os.walk(
            root, topdown=True, onerror=None, followlinks=False
        ):
            if stop_check and stop_check():
                if log_cb:
                    log_cb("Scan cancelled by user.", "warning")
                found_files.sort(key=lambda x: x["size_bytes"], reverse=True)
                return found_files[:top_n]

            # Filter out system/protected dirs and hidden $-prefixed dirs
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in skip_dirs and not d.startswith("$")
            ]

            scanned_dirs += 1
            if scanned_dirs % 1500 == 0 and log_cb:
                log_cb(
                    f"Scanned {scanned_dirs} directories... (Found {len(found_files)} large files)",
                    "info"
                )

            for f in filenames:
                try:
                    full_path = os.path.join(dirpath, f)
                    # Skip symlinks — they may point elsewhere
                    if os.path.islink(full_path):
                        continue
                    size = os.path.getsize(full_path)
                    if size >= min_bytes:
                        drive_letter = os.path.splitdrive(full_path)[0].upper()
                        _, ext = os.path.splitext(f)
                        found_files.append({
                            "name": f,
                            "drive": drive_letter,
                            "path": full_path,
                            "size_bytes": size,
                            "size_mb": round(size / (1024 * 1024), 1),
                            "size_gb": round(size / (1024 ** 3), 2),
                            "ext": ext.lower(),
                        })
                except (OSError, PermissionError):
                    continue

    found_files.sort(key=lambda x: x["size_bytes"], reverse=True)
    top_results = found_files[:top_n]

    if log_cb:
        log_cb(
            f"Scan complete. Found {len(found_files)} files >= {min_size_mb} MB "
            f"across {', '.join(roots)}. Showing top {len(top_results)}.",
            "success"
        )

    return top_results


# Backward-compatibility alias
def scan_large_files_python(
    root: str = "C:\\",
    min_size_mb: float = 50.0,
    top_n: int = 20,
    log_cb: Optional[Callable[[str, str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> List[Dict]:
    return scan_large_files_multi([root], min_size_mb, top_n, log_cb, stop_check)
