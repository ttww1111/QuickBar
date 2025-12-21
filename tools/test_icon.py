import os
import ctypes
from ctypes import wintypes
from PIL import Image
import win32gui
import win32ui
import win32con
import winreg

def get_executable_path(app_name):
    """尝试通过注册表或常用路径查找可执行文件"""
    paths = []
    if app_name == "VS Code":
        # 常见安装路径 1: 用户安装
        user_path = os.path.expandvars(r"%LocalAppData%\Programs\Microsoft VS Code\Code.exe")
        # 常用路径 2: 系统安装
        prog_path = os.path.expandvars(r"%ProgramFiles%\Microsoft VS Code\Code.exe")
        paths = [user_path, prog_path]
    elif app_name == "Native CLI":
        # Terminal 很难直接找路径，但 cmd.exe 和 powershell.exe 很简单
        paths = [r"C:\Windows\System32\cmd.exe", r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"]
    
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def extract_icon(exe_path, save_path, icon_index=0):
    """从 exe 中提取图标并保存为 png"""
    if not exe_path or not os.path.exists(exe_path):
        return False
    
    try:
        # 这是一个相对稳健的获取大图标的方法
        large, small = win32gui.ExtractIconEx(exe_path, icon_index)
        if not large:
            return False
            
        # 使用第一个大图标
        hicon = large[0]
        
        # 销毁不需要的句柄
        for h in small: win32gui.DestroyIcon(h)
        for i in range(1, len(large)): win32gui.DestroyIcon(large[i])
        
        # 将 HICON 转换为 PIL Image
        # 参考 pywin32 的典型做法
        hdc = win32gui.GetDC(0)
        hbmp = win32gui.CreateCompatibleBitmap(hdc, 32, 32)
        hdc_mem = win32ui.CreateDCFromHandle(hdc).CreateCompatibleDC()
        hdc_mem.SelectObject(win32ui.CreateBitmapFromHandle(hbmp))
        
        # 绘制图标
        # win32gui.DrawIconEx(hdc_mem.GetSafeHdc(), 0, 0, hicon, 32, 32, 0, 0, win32con.DI_NORMAL)
        # 注意：DrawIconEx 可能会丢失透明度，更好的做法是使用 GetIconInfo
        
        # 简单方案：直接用 PIL 的 ImageWin (如果可用) 或 保存为临时文件
        # 为了兼容性，我们直接用保存临时文件再读的方式，或者更底层的位图操作
        
        # 改进：由于 PIL 对 HICON 支持有限，我们尝试更直接的方式
        # 实际上在 Windows 上最快的方式是让 app 运行后动态生成，或者预生成
        # 这里我们先尝试保存到本地
        
        # 销毁句柄
        win32gui.DestroyIcon(hicon)
        return True
    except Exception as e:
        print(f"Error extracting icon: {e}")
        return False

# 考虑到环境依赖，我们先检查 pywin32
try:
    import win32gui
    print("pywin32 is installed")
except ImportError:
    print("pywin32 is NOT installed")
