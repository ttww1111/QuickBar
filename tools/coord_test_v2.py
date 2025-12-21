import sys
import time
import ctypes
from pywinauto import Desktop

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_mouse_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def get_relative_coord():
    print("--- 坐标比例计算实验 (修正版) ---")
    print("准备开始：请在 3 秒内将鼠标停在 Claude 的输入框上不要动...")
    
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    mx, my = get_mouse_pos()
    
    try:
        windows = Desktop(backend="uia").windows(title_re=".*Visual Studio Code.*")
        if not windows:
            print("错误: 未找到 VS Code 窗口。")
            return
        
        vscode = windows[0]
        rect = vscode.rectangle()
        
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        
        rel_x = (mx - rect.left) / width
        rel_y = (my - rect.top) / height
        
        print(f"\n记录成功！")
        print(f"窗口范围: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
        print(f"鼠标屏幕位置: ({mx}, {my})")
        print(f"相对百分比位置: X={rel_x:.4f}, Y={rel_y:.4f}")
        print("-" * 30)
    except Exception as e:
        print(f"运行失败: {e}")

if __name__ == "__main__":
    get_relative_coord()
