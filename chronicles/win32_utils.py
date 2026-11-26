"""Windows native API helpers: DPI, click-through, mutex, COM shortcuts, registry, process control."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import sys
from typing import Optional

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication

from version import APP_AUTHOR, APP_NAME, APP_USER_MODEL_ID, APP_VERSION

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
ERROR_ALREADY_EXISTS = 183
UNINSTALL_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ChroniclesRaidTimer"


def init_windows_platform() -> None:
    """Enable per-monitor DPI awareness and set Windows AppUserModelID."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


class SingleInstanceGuard:
    """Native Windows named mutex guard preventing duplicate app instances."""

    def __init__(self, mutex_name: str):
        self._handle: Optional[int] = None
        self.already_running = False
        if sys.platform != "win32":
            return
        try:
            handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
            self._handle = handle
            if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                self.already_running = True
        except Exception:
            pass

    def release(self) -> None:
        if sys.platform == "win32" and self._handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self._handle)
            except Exception:
                pass
            self._handle = None


def set_click_through(hwnd: int, enabled: bool) -> None:
    """Toggle WS_EX_TRANSPARENT on a native window handle."""
    if sys.platform != "win32" or not hwnd:
        return
    try:
        user32 = ctypes.windll.user32
        user32.GetWindowLongPtrW.restype = ctypes.c_longlong
        user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetWindowLongPtrW.restype = ctypes.c_longlong
        user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong]

        current = user32.GetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
        if enabled:
            new_style = current | WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            new_style = current & ~WS_EX_TRANSPARENT
        user32.SetWindowLongPtrW(ctypes.c_void_p(hwnd), GWL_EXSTYLE, ctypes.c_longlong(new_style))
    except Exception:
        pass


def clamp_to_screens(x: int, y: int, width: int, height: int) -> tuple[int, int]:
    """Ensure the window remains visible on at least one active monitor."""
    screens = QApplication.screens()
    if not screens:
        return x, y

    rect = QRect(x, y, max(80, width), max(40, height))
    for scr in screens:
        avail = scr.availableGeometry()
        if avail.intersects(rect):
            clamped_x = max(avail.left() - width + 60, min(x, avail.right() - 60))
            clamped_y = max(avail.top(), min(y, avail.bottom() - 40))
            return clamped_x, clamped_y

    primary = QApplication.primaryScreen()
    if primary:
        avail = primary.availableGeometry()
        return avail.left() + 80, avail.top() + 80
    return 80, 80


def snap_position_to_edges(
    pos: QPoint, width: int, height: int, threshold: int = 16
) -> QPoint:
    """Magnetically snap a window's edges to the nearest monitor availableGeometry."""
    screens = QApplication.screens()
    if not screens:
        return pos

    center = QPoint(pos.x() + width // 2, pos.y() + height // 2)
    target_avail = None
    for scr in screens:
        if scr.availableGeometry().contains(center):
            target_avail = scr.availableGeometry()
            break
    if target_avail is None:
        primary = QApplication.primaryScreen()
        if primary is None:
            return pos
        target_avail = primary.availableGeometry()

    nx, ny = pos.x(), pos.y()
    margin = 10

    if abs(nx - (target_avail.left() + margin)) <= threshold:
        nx = target_avail.left() + margin
    elif abs((nx + width) - (target_avail.right() - margin)) <= threshold:
        nx = target_avail.right() - margin - width

    if abs(ny - (target_avail.top() + margin)) <= threshold:
        ny = target_avail.top() + margin
    elif abs((ny + height) - (target_avail.bottom() - margin)) <= threshold:
        ny = target_avail.bottom() - margin - height

    return QPoint(nx, ny)


def set_windows_startup(enabled: bool, exe_override: Optional[str] = None) -> bool:
    """Enable or disable current-user Windows autostart in HKCU Run."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                if exe_override:
                    cmd = f'"{exe_override}"'
                elif getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    app_py = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"
                    )
                    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
                    runner = pythonw if os.path.exists(pythonw) else sys.executable
                    cmd = f'"{runner}" "{app_py}"'
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False


def create_windows_shortcut(
    target_path: str,
    link_path: str,
    arguments: str = "",
    description: str = "",
    working_dir: str = "",
    icon_path: str = "",
) -> bool:
    """Create a Windows .lnk shortcut using pure Win32 COM IShellLinkW (no child shells)."""
    if sys.platform != "win32":
        return False

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    clsid_shell_link = GUID(0x00021401, 0x0000, 0x0000, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
    iid_shell_link = GUID(0x000214F9, 0x0000, 0x0000, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
    iid_persist_file = GUID(0x0000010B, 0x0000, 0x0000, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))

    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)
    shell_link = ctypes.c_void_p()
    persist = ctypes.c_void_p()
    try:
        os.makedirs(os.path.dirname(link_path), exist_ok=True)
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid_shell_link),
            None,
            1,
            ctypes.byref(iid_shell_link),
            ctypes.byref(shell_link),
        )
        if hr != 0 or not shell_link:
            return False

        vtbl = ctypes.cast(shell_link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        query_if = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(vtbl[0])
        release_sl = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
        set_desc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtbl[7])
        set_wdir = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtbl[9])
        set_args = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtbl[11])
        set_icon = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int)(vtbl[17])
        set_path = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p)(vtbl[20])

        set_path(shell_link, target_path)
        if arguments:
            set_args(shell_link, arguments)
        if description:
            set_desc(shell_link, description)
        set_wdir(shell_link, working_dir or os.path.dirname(target_path))
        if icon_path and os.path.exists(icon_path):
            set_icon(shell_link, icon_path, 0)

        hr_qi = query_if(shell_link, ctypes.byref(iid_persist_file), ctypes.byref(persist))
        if hr_qi != 0 or not persist:
            release_sl(shell_link)
            return False

        p_vtbl = ctypes.cast(persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        release_pf = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(p_vtbl[2])
        save_pf = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, wintypes.BOOL)(p_vtbl[6])
        hr_save = save_pf(persist, link_path, True)
        release_pf(persist)
        release_sl(shell_link)
        return hr_save == 0
    except Exception:
        return False
    finally:
        ole32.CoUninitialize()


def register_windows_uninstall(
    install_dir: str,
    exe_path: str,
    icon_path: str,
    estimated_kb: int = 120000,
) -> bool:
    """Register Chronicles Raid Timer in HKCU Installed Apps (Add/Remove Programs)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_REG_KEY) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_AUTHOR)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, icon_path)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{exe_path}" --uninstall')
            winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{exe_path}" --uninstall --silent')
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, max(1024, int(estimated_kb)))
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        return True
    except Exception:
        return False


def unregister_windows_uninstall() -> bool:
    """Remove Chronicles Raid Timer from HKCU Installed Apps."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_REG_KEY)
        return True
    except FileNotFoundError:
        return True
    except Exception:
        return False


def terminate_other_app_instances(exe_name: str = "ChroniclesRaidTimer.exe") -> int:
    """Close running instances of exe_name cleanly via Win32 Toolhelp32 (excluding current PID)."""
    if sys.platform != "win32":
        return 0

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snap == ctypes.c_void_p(-1).value:
        return 0

    closed = 0
    my_pid = os.getpid()
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                if entry.szExeFile.lower() == exe_name.lower() and entry.th32ProcessID != my_pid:
                    proc = kernel32.OpenProcess(0x0001 | 0x00100000, False, entry.th32ProcessID)
                    if proc:
                        try:
                            if kernel32.TerminateProcess(proc, 0):
                                kernel32.WaitForSingleObject(proc, 1500)
                                closed += 1
                        finally:
                            kernel32.CloseHandle(proc)
                if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(snap)
    return closed
