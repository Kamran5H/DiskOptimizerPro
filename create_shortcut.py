import os
import sys
import subprocess

def create_desktop_shortcut():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Resolve desktop path dynamically (checking OneDrive and User Profile)
    user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    onedrive = os.environ.get("OneDrive", "")
    onedrive_desktop = os.path.join(onedrive, "Desktop") if onedrive else ""
    user_desktop = os.path.join(user_profile, "Desktop")

    def ps_quote(p: str) -> str:
        return p.replace("'", "''")

    if onedrive_desktop and os.path.exists(onedrive_desktop):
        desktop = onedrive_desktop
    elif os.path.exists(user_desktop):
        desktop = user_desktop
    else:
        desktop = user_profile

    ico_path = os.path.join(app_dir, "assets", "app_icon.ico")
    shortcut_path = os.path.join(desktop, "Disk Optimizer Pro.lnk")
    portable_exe = os.path.join(app_dir, "DiskOptimizerPro.exe")
    if os.path.isfile(portable_exe):
        target_path = portable_exe
        arguments = ""
    else:
        launcher_pyw = os.path.join(app_dir, "launcher.pyw")
        py_dir = os.path.dirname(sys.executable)
        pythonw = os.path.join(py_dir, "pythonw.exe")
        target_path = pythonw if os.path.isfile(pythonw) else sys.executable
        arguments = f'"{ps_quote(launcher_pyw)}"'

    ps_script = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{ps_quote(shortcut_path)}')
    $Shortcut.TargetPath = '{ps_quote(target_path)}'
    $Shortcut.Arguments = '{arguments}'
    $Shortcut.WorkingDirectory = '{ps_quote(app_dir)}'
    $Shortcut.IconLocation = '{ps_quote(ico_path)},0'
    $Shortcut.Description = 'Disk Optimizer Pro - Windows storage and memory overview'
    $Shortcut.Save()
    """

    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True
    )
    if res.returncode == 0 and os.path.exists(shortcut_path):
        print(f"Desktop shortcut created successfully:\n{shortcut_path}")
        return True
    else:
        print(f"Error creating shortcut: {res.stderr}")
        return False

if __name__ == "__main__":
    create_desktop_shortcut()
