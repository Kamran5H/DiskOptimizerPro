import os
import sys
import ctypes

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    # If not running as administrator, request UAC elevation
    if not is_admin():
        # Re-launch with 'runas' to trigger UAC elevation prompt
        try:
            # We target this script itself
            script = os.path.abspath(__file__)
            # Prefer pythonw.exe if available to keep it clean and windowless
            python_exe = sys.executable
            if python_exe.lower().endswith("python.exe"):
                pyw = python_exe[:-4] + "w.exe"
                if os.path.exists(pyw):
                    python_exe = pyw

            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",
                python_exe,
                f'"{script}"',
                base_dir,
                1  # SW_SHOWNORMAL
            )
            # If successfully requested elevation (ret > 32), exit this unelevated process
            if ret > 32:
                sys.exit(0)
        except Exception:
            pass  # If user clicks No on UAC, continue running in standard mode

    # Start the application
    from gui.app import main as run_app
    run_app()

if __name__ == "__main__":
    main()
