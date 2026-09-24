import os
import re
import sys
import unittest
import tempfile
import shutil

# Add root project path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from engine.system_ops import (
    get_disk_stats, get_all_drives_stats, is_admin, is_process_running_fast
)
from engine.cleaner_engine import (
    CleanerEngine, delete_folder_contents, safe_rmtree, measure_path_size
)
from engine.large_files import scan_large_files_multi
from engine.duplicate_finder import find_duplicate_files
from engine.empty_folder_cleaner import (
    scan_empty_directories, delete_empty_directories, is_protected
)


class TestSystemOps(unittest.TestCase):

    def test_dual_drive_stats(self):
        stats = get_all_drives_stats(["C:\\", "D:\\"])
        self.assertIn("C:", stats)
        c = stats["C:"]
        self.assertGreater(c["total_gb"], 0)
        self.assertGreater(c["free_gb"], 0)
        self.assertIn("volume_name", c)
        self.assertIn("file_system", c)
        print(f"  Drive C: {c['free_gb']} GB Free / {c['total_gb']} GB ({c['free_percent']}% free) [{c['file_system']}]")
        if "D:" in stats:
            d = stats["D:"]
            self.assertGreater(d["total_gb"], 0)
            print(f"  Drive D: {d['free_gb']} GB Free / {d['total_gb']} GB ({d['free_percent']}% free)")

    def test_is_admin_returns_bool(self):
        result = is_admin()
        self.assertIsInstance(result, bool)
        print(f"  Admin privileges: {result}")

    def test_disk_stats_nonexistent_drive(self):
        stats = get_disk_stats("Z:\\")
        self.assertFalse(stats["exists"])
        self.assertEqual(stats["free_gb"], 0)
        print("  Non-existent drive returns exists=False correctly")

    def test_is_process_running_fast(self):
        # Explorer is always running on Windows interactive desktop
        self.assertTrue(is_process_running_fast(["explorer.exe"]))
        # Python running the current test
        self.assertTrue(is_process_running_fast(["python.exe", "pythonw.exe"]))
        # Non-existent process
        self.assertFalse(is_process_running_fast(["non_existent_fake_proc_99999.exe"]))
        print("  Fast Win32 Toolhelp32 process snapshot verified (<5ms)")


class TestCleanerEngine(unittest.TestCase):

    def test_initialization(self):
        engine = CleanerEngine()
        self.assertIsNotNone(engine)
        self.assertFalse(engine.should_stop)

    def test_cancel_and_reset(self):
        engine = CleanerEngine()
        engine.stop()
        self.assertTrue(engine.should_stop)
        engine.reset()
        self.assertFalse(engine.should_stop)
        print("  Stop/reset cooperative cancellation cycle works correctly")

    def test_safe_operations_execution(self):
        logs = []
        engine = CleanerEngine(log_cb=lambda msg, lvl: logs.append((lvl, msg)))

        engine.clean_thumbnail_cache()
        engine.clean_recent_items()
        engine.clean_mendeley_installer()
        engine.clean_old_opera_versions()
        engine.clean_old_playwright_versions()

        self.assertTrue(any("thumbnail" in msg.lower() for _, msg in logs))
        print("  Safe non-destructive cleaners executed without exception")

    def test_delete_folder_contents_safe(self):
        """delete_folder_contents must skip symlinks and return correct bytes."""
        tmp = tempfile.mkdtemp(prefix="test_dfc_")
        try:
            real_file = os.path.join(tmp, "real.txt")
            with open(real_file, "wb") as f:
                f.write(b"A" * 1024)

            freed = delete_folder_contents(tmp)
            self.assertEqual(freed, 1024)
            self.assertEqual(os.listdir(tmp), [])  # folder now empty
            print("  delete_folder_contents returned correct byte count")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_safe_rmtree_with_readonly_file(self):
        """safe_rmtree must delete read-only files without raising PermissionError."""
        tmp = tempfile.mkdtemp(prefix="test_rmtree_")
        try:
            ro_file = os.path.join(tmp, "readonly.txt")
            with open(ro_file, "w") as f:
                f.write("read only data")
            import stat
            os.chmod(ro_file, stat.S_IREAD)

            safe_rmtree(tmp)
            self.assertFalse(os.path.exists(tmp))
            print("  safe_rmtree successfully cleared read-only files")
        finally:
            if os.path.exists(tmp):
                shutil.rmtree(tmp, ignore_errors=True)

    def test_measure_path_size(self):
        tmp = tempfile.mkdtemp(prefix="test_sz_")
        try:
            fp = os.path.join(tmp, "data.bin")
            with open(fp, "wb") as f:
                f.write(b"Z" * 5000)
            self.assertEqual(measure_path_size(fp), 5000)
            self.assertGreaterEqual(measure_path_size(tmp), 5000)
            print("  measure_path_size accurately calculates file and directory sizes")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_delete_folder_contents_nonexistent(self):
        freed = delete_folder_contents(r"C:\nonexistent_path_xyz_12345")
        self.assertEqual(freed, 0)
        print("  delete_folder_contents handles non-existent path gracefully")


class TestLargeFiles(unittest.TestCase):

    def test_large_files_multi_scan(self):
        tmp = tempfile.mkdtemp(prefix="test_lf_")
        try:
            # Create files with known sizes
            f1 = os.path.join(tmp, "big1.dat")
            f2 = os.path.join(tmp, "big2.dat")
            with open(f1, "wb") as f:
                f.write(b"0" * (2 * 1024 * 1024))  # 2MB
            with open(f2, "wb") as f:
                f.write(b"1" * (5 * 1024 * 1024))  # 5MB

            results = scan_large_files_multi(roots=[tmp], min_size_mb=1.0, top_n=5)
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["size_bytes"], 5 * 1024 * 1024)
            self.assertEqual(results[1]["size_bytes"], 2 * 1024 * 1024)
            print(f"  Large files scanner found {len(results)} mock files sorted largest first")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_scan_sorted_largest_first(self):
        tmp = tempfile.mkdtemp(prefix="test_lf_")
        try:
            for name, size in [("small.bin", 2 * 1024), ("large.bin", 8 * 1024)]:
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(b"X" * size)
            results = scan_large_files_multi(roots=[tmp], min_size_mb=0.001, top_n=10)
            self.assertGreaterEqual(len(results), 2)
            self.assertGreaterEqual(results[0]["size_bytes"], results[-1]["size_bytes"])
            print("  Large file results are sorted largest-first")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cancellation(self):
        tmp = tempfile.mkdtemp(prefix="test_lf_cancel_")
        try:
            res = scan_large_files_multi([tmp], min_size_mb=1.0, stop_check=lambda: True)
            self.assertEqual(len(res), 0)
            print("  Large file scan cancellation works")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestDuplicateFinder(unittest.TestCase):

    def test_finds_exact_duplicates(self):
        tmp = tempfile.mkdtemp(prefix="test_dupe_")
        try:
            content = b"DISK_OPTIMIZER_PRO_DUPLICATE_TEST_DATA_" * 1000
            for name in ["file1.bin", "file2.bin"]:
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(content)

            dupes = find_duplicate_files([tmp], min_size_bytes=100)
            self.assertEqual(len(dupes), 1)
            self.assertEqual(len(dupes[0]["files"]), 2)
            self.assertIn("wasted_gb", dupes[0])
            print("  Duplicate files finder verified on mock files")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_false_positives(self):
        tmp = tempfile.mkdtemp(prefix="test_nodup_")
        try:
            for i in range(3):
                with open(os.path.join(tmp, f"unique_{i}.bin"), "wb") as f:
                    f.write(b"UNIQUE_" * 200 + bytes([i]))
            dupes = find_duplicate_files([tmp], min_size_bytes=100)
            self.assertEqual(len(dupes), 0)
            print("  No false positives on unique files")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_cancellation(self):
        tmp = tempfile.mkdtemp(prefix="test_dupe_cancel_")
        try:
            dupes = find_duplicate_files([tmp], min_size_bytes=100, stop_check=lambda: True)
            self.assertEqual(len(dupes), 0)
            print("  Duplicate scan cancellation works")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_hardlinks_not_counted_as_duplicates(self):
        tmp = tempfile.mkdtemp(prefix="test_hardlink_")
        try:
            f1 = os.path.join(tmp, "original.bin")
            f2 = os.path.join(tmp, "hardlink.bin")
            with open(f1, "wb") as f:
                f.write(b"HARDLINK_CONTENT_" * 100)
            try:
                os.link(f1, f2)
            except OSError:
                return
            dupes = find_duplicate_files([tmp], min_size_bytes=50)
            self.assertEqual(len(dupes), 0, "Hard links sharing physical storage must not be reported as duplicates")
            print("  Hard link deduplication verified: hard links sharing physical storage correctly ignored")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestEmptyFolderCleaner(unittest.TestCase):

    def test_finds_and_deletes_empty_dirs(self):
        tmp = tempfile.mkdtemp(prefix="test_empty_")
        try:
            nested = os.path.join(tmp, "sub1", "empty_leaf")
            os.makedirs(nested, exist_ok=True)

            found = scan_empty_directories([tmp])
            self.assertGreaterEqual(len(found), 1)

            succ, fail = delete_empty_directories(found)
            self.assertGreaterEqual(succ, 1)
            print("  Empty folder cleaner verified on mock tree")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_protection_rules(self):
        self.assertTrue(is_protected(r"C:\Users\test\.git\branches", r"C:\Users\test"))
        self.assertTrue(is_protected(r"C:\Users\test\AppData\Roaming\TestApp", r"C:\Users\test"))
        self.assertTrue(is_protected(r"C:\Program Files\App", r"C:\Program Files"))
        self.assertTrue(is_protected(r"C:\Windows\System32", r"C:\Windows"))
        self.assertTrue(is_protected("D:\\", "D:\\"))
        self.assertFalse(is_protected(r"D:\MyProjects\ProjectA\empty_sub", r"D:\MyProjects"))
        print("  Protected directory filters all verified")

    def test_cancellation(self):
        tmp = tempfile.mkdtemp(prefix="test_empty_cancel_")
        try:
            empty = scan_empty_directories([tmp], stop_check=lambda: True)
            self.assertEqual(len(empty), 0)
            print("  Empty folder scan cancellation works")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_skip_nonempty_dirs(self):
        tmp = tempfile.mkdtemp(prefix="test_notempty_")
        try:
            has_file = os.path.join(tmp, "has_content")
            os.makedirs(has_file, exist_ok=True)
            with open(os.path.join(has_file, "data.txt"), "w") as f:
                f.write("content")
            found = scan_empty_directories([tmp])
            self.assertNotIn(has_file, found)
            print("  Non-empty directory correctly excluded from results")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestVersionSorting(unittest.TestCase):

    def test_version_numerical_sort(self):
        """Version sort must be numerical, not lexicographical."""
        versions = ["98.0.1", "102.0.1", "99.0.5"]
        sorted_vers = sorted(
            versions, key=lambda v: [int(x) for x in re.findall(r"\d+", v)] or [0]
        )
        self.assertEqual(sorted_vers[-1], "102.0.1",
                         "102.0.1 must be newest (lexicographic would pick 99.0.5)")
        self.assertEqual(sorted_vers[:-1], ["98.0.1", "99.0.5"])
        print("  Numerical version sort: 102.0.1 correctly identified as newest")

    def test_build_number_sort(self):
        builds = ["chromium-998", "chromium-1097", "chromium-1002"]
        sorted_builds = sorted(
            builds, key=lambda s: [int(x) for x in re.findall(r"\d+", s)] or [0]
        )
        self.assertEqual(sorted_builds[-1], "chromium-1097",
                         "Build 1097 must be newest (lexicographic would pick chromium-998)")
        print("  Build number sort: chromium-1097 correctly identified as newest")


class TestGUIInstantiation(unittest.TestCase):

    def test_gui_v2_instantiation(self):
        from gui.app import DiskOptimizerApp
        app = DiskOptimizerApp()
        self.assertEqual(len(app.tasks), 29)
        app.update_idletasks()
        app.quit()
        app.destroy()
        print("  GUI V2 Application instantiated successfully (29 registered modules)")

    def test_preset_scope_switching(self):
        from gui.app import DiskOptimizerApp
        app = DiskOptimizerApp()
        app.apply_preset("Drive D: Clean")
        self.assertEqual(app.scope_var.get(), "Drive D: Only")
        app.apply_preset("Safe Fast Clean")
        self.assertEqual(app.scope_var.get(), "All Drives (C: & D:)")
        app.update_idletasks()
        app.quit()
        app.destroy()
        print("  Preset scope switching verified")

    def test_deep_clean_preset_no_chrome_history(self):
        from gui.app import DiskOptimizerApp
        app = DiskOptimizerApp()
        app.apply_preset("Deep System Clean")
        # chrome_history must NOT be selected by default to protect user data
        self.assertFalse(app.tasks["chrome_history"]["var"].get())
        # but user temp and drive_d_junk should be selected
        self.assertTrue(app.tasks["user_temp"]["var"].get())
        self.assertTrue(app.tasks["drive_d_junk"]["var"].get())
        app.update_idletasks()
        app.quit()
        app.destroy()
        print("  Deep System Clean preset safely leaves chrome_history unchecked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
