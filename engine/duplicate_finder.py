import os
import hashlib
from typing import List, Dict, Callable, Optional
from collections import defaultdict


def compute_chunk_hash(filepath: str, max_bytes: int = 4096) -> str:
    """Computes SHA-256 hash of the first max_bytes of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        chunk = f.read(max_bytes)
        hasher.update(chunk)
    return hasher.hexdigest()


def compute_full_hash(filepath: str, chunk_size: int = 65536) -> str:
    """Computes complete SHA-256 hash of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def find_duplicate_files(
    roots: List[str],
    min_size_bytes: int = 1024 * 1024,   # 1 MB default
    max_results: int = 100,
    log_cb: Optional[Callable[[str, str], None]] = None,
    stop_check: Optional[Callable[[], bool]] = None
) -> List[Dict]:
    """
    High-performance 3-stage duplicate file scanner:
      Stage 1: Group files by size              (zero I/O overhead)
      Stage 2: Hash first 4 KB for candidates   (fast pre-filter)
      Stage 3: Full SHA-256 for confirmed pairs  (accurate)

    Returns list of duplicate groups sorted by total wasted space (descending):
    [
        {
            "hash": "...",
            "file_size": int,
            "size_mb": float,
            "wasted_bytes": int,
            "wasted_mb": float,
            "wasted_gb": float,
            "count": int,
            "files": ["path1", "path2", ...]
        }
    ]
    """
    if isinstance(min_size_bytes, bool) or not isinstance(min_size_bytes, int) or min_size_bytes < 0:
        raise ValueError("min_size_bytes must be a non-negative integer")
    if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results < 0:
        raise ValueError("max_results must be a non-negative integer")

    skip_dirs = {
        "$recycle.bin", "system volume information", "recovery", "windows",
        "program files", "program files (x86)", "appdata"
    }

    if log_cb:
        log_cb(
            f"Scanning for duplicate files across {', '.join(roots)} "
            f"(Min size: {round(min_size_bytes / (1024 * 1024), 1)} MB)...",
            "step"
        )

    # ----------------------------------------------------------------
    # STAGE 1 — Collect files, grouped by size
    # ----------------------------------------------------------------
    size_map: Dict[int, List[str]] = defaultdict(list)
    seen_inodes = set()
    scanned_count = 0

    for root_dir in roots:
        if not os.path.isdir(root_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True, followlinks=False):
            if stop_check and stop_check():
                if log_cb:
                    log_cb("Scan cancelled by user.", "warning")
                return []

            # Filter protected / system dirs
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in skip_dirs and not d.startswith("$")
            ]

            for f in filenames:
                try:
                    p = os.path.join(dirpath, f)
                    if os.path.islink(p):   # skip symlinks
                        continue
                    st = os.stat(p)
                    sz = st.st_size
                    if sz >= min_size_bytes:
                        # Avoid counting hard-links as distinct duplicate copies
                        inode_key = (st.st_dev, st.st_ino)
                        if inode_key in seen_inodes and st.st_nlink > 1:
                            continue
                        seen_inodes.add(inode_key)
                        size_map[sz].append(p)
                        scanned_count += 1
                except (OSError, PermissionError):
                    continue

    if log_cb:
        log_cb(
            f"Stage 1 complete: Examined {scanned_count} candidate files. "
            "Analysing potential duplicate groups...",
            "info"
        )

    # Filter to only sizes with ≥ 2 files
    candidate_groups = {sz: paths for sz, paths in size_map.items() if len(paths) > 1}
    if not candidate_groups:
        if log_cb:
            log_cb("No files with matching sizes found.", "info")
        return []

    # ----------------------------------------------------------------
    # STAGE 2 — Partial hash (first 4 KB)
    # ----------------------------------------------------------------
    head_map: Dict = defaultdict(list)
    for sz, paths in candidate_groups.items():
        if stop_check and stop_check():
            if log_cb:
                log_cb("Scan cancelled by user.", "warning")
            return []
        for p in paths:
            try:
                head_h = compute_chunk_hash(p, 4096)
                head_map[(sz, head_h)].append(p)
            except (OSError, PermissionError):
                continue

    potential_dupes = {k: v for k, v in head_map.items() if len(v) > 1}

    # ----------------------------------------------------------------
    # STAGE 3 — Full SHA-256 verification
    # ----------------------------------------------------------------
    if log_cb:
        log_cb(
            f"Stage 2 complete: Verifying {len(potential_dupes)} candidate groups "
            "with full SHA-256...",
            "info"
        )

    exact_duplicates: Dict = defaultdict(list)
    for (sz, _), paths in potential_dupes.items():
        if stop_check and stop_check():
            if log_cb:
                log_cb("Scan cancelled by user.", "warning")
            return []
        for p in paths:
            try:
                full_h = compute_full_hash(p)
                exact_duplicates[(sz, full_h)].append(p)
            except (OSError, PermissionError):
                continue

    # ----------------------------------------------------------------
    # BUILD RESULT LIST
    # ----------------------------------------------------------------
    results: List[Dict] = []
    for (sz, full_h), paths in exact_duplicates.items():
        if len(paths) > 1:
            wasted = sz * (len(paths) - 1)
            results.append({
                "hash": full_h[:12],
                "file_size": sz,
                "size_mb": round(sz / (1024 * 1024), 2),
                "wasted_bytes": wasted,
                "wasted_mb": round(wasted / (1024 * 1024), 2),
                "wasted_gb": round(wasted / (1024 ** 3), 3),
                "count": len(paths),
                "files": paths
            })

    results.sort(key=lambda x: x["wasted_bytes"], reverse=True)
    top_dupes = results[:max_results]

    total_wasted_mb = round(sum(r["wasted_mb"] for r in top_dupes), 1)
    if log_cb:
        log_cb(
            f"Duplicate scan complete! Found {len(top_dupes)} duplicate sets "
            f"(~{total_wasted_mb} MB wasted space).",
            "success"
        )

    return top_dupes
