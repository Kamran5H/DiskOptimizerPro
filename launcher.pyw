import os
import sys

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    # Run with normal user permissions; request elevation only for an explicit action.
    from gui.app import main as run_app
    run_app()

if __name__ == "__main__":
    main()
