import sys
from pywinauto import Desktop

def deep_inspect():
    print("--- VS Code 深度 UI 树扫描 ---")
    try:
        windows = Desktop(backend="uia").windows(title_re=".*Visual Studio Code.*")
        if not windows:
            print("未找到 VS Code 窗口。")
            return
        
        vscode = windows[0]
        print(f"锁定窗口: {vscode.window_text()}")
        
        # 打印前 5 层子元素，看看 Webview 到底躲在哪里
        print("正在递归获取子元素结构...")
        
        def print_children(element, depth=0, max_depth=3):
            if depth > max_depth:
                return
            
            indent = "  " * depth
            try:
                # 获取基本信息
                ctrl_type = element.control_type()
                name = element.window_text() or "无名称"
                print(f"{indent}[{ctrl_type}] Name: {name}")
                
                # 如果发现 Pane 或 Custom，继续深入
                for child in element.children():
                    print_children(child, depth + 1, max_depth)
            except:
                pass

        print_children(vscode)
        print("-" * 30)
        print("尝试直接搜索名为 'Claude' 的控件...")
        claude_elements = vscode.descendants(title_re=".*Claude.*")
        for i, el in enumerate(claude_elements):
            print(f"找到疑似 Claude 元素 [{i}]: {el.control_type()} - {el.window_text()}")

    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    deep_inspect()
