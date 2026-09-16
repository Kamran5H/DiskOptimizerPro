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

    if onedrive_desktop and os.path.exists(onedrive_desktop):
        desktop = onedrive_desktop
    elif os.path.exists(user_desktop):
        desktop = user_desktop
    else:
        desktop = user_profile

    launcher_pyw = os.path.join(app_dir, "launcher.pyw")
    ico_path = os.path.join(app_dir, "assets", "app_icon.ico")
    shortcut_path = os.path.join(desktop, "Disk Optimizer Pro - Kamran Ashraf.lnk")

    # Find pythonw.exe
    py_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(py_dir, "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    ps_script = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
    $Shortcut.TargetPath = '{pythonw}'
    $Shortcut.Arguments = '"{launcher_pyw}"'
    $Shortcut.WorkingDirectory = '{app_dir}'
    $Shortcut.IconLocation = '{ico_path},0'
    $Shortcut.Description = 'Disk Optimizer Pro - 1-Click PC Cleanup & Optimization Suite'
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
