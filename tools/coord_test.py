import sys
import time
from pywinauto import Desktop, mouse

def get_relative_coord():
    print("--- 坐标比例计算实验 ---")
    print("准备开始：请在 3 秒内将鼠标停在 Claude 的输入框上不要动...")
    
    # 简单的倒计时
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    # 获取当前鼠标位置
    mx, my = mouse.position()
    
    # 获取 VS Code 窗口位置
    try:
        windows = Desktop(backend="uia").windows(title_re=".*Visual Studio Code.*")
        if not windows:
            print("错误: 未找到 VS Code 窗口。")
            return
        
        vscode = windows[0]
        rect = vscode.rectangle()
        
        # 计算百分比
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        
        if width == 0 or height == 0:
            print("错误: 窗口尺寸无效。")
            return
            
        rel_x = (mx - rect.left) / width
        rel_y = (my - rect.top) / height
        
        print(f"\n记录成功！")
        print(f"窗口范围（左, 上, 右, 下）: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
        print(f"鼠标屏幕位置: ({mx}, {my})")
        print(f"相对百分比位置: X={rel_x:.4f} ({rel_x:.2%}), Y={rel_y:.4f} ({rel_y:.2%})")
        print("-" * 30)
        print("请把上面那行 '相对百分比位置' 发给我。")
    except Exception as e:
        print(f"运行失败: {e}")

if __name__ == "__main__":
    get_relative_coord()
