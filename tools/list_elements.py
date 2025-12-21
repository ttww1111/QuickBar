import sys
from pywinauto import Desktop

def list_all_descendants():
    print("--- 扫描 VS Code 所有可见文本 ---")
    try:
        windows = Desktop(backend="uia").windows(title_re=".*Visual Studio Code.*")
        if not windows:
            print("未找到 VS Code 窗口。")
            return
        
        vscode = windows[0]
        print(f"锁定窗口: {vscode.window_text()}")
        
        # 获取所有后代元素，不设限，打印所有非空的 window_text
        print("正在搜寻包含 'Claude' 或 'Ask' 字样的元素...")
        all_elements = vscode.descendants()
        found = False
        for el in all_elements:
            try:
                name = el.window_text()
                if name and any(keyword in name for keyword in ["Claude", "Ask", "chat", "输入"]):
                    print(f"找到匹配元素: [{el.control_type()}] Name: '{name}' | AutoID: {el.automation_id()}")
                    found = True
            except:
                continue
        
        if not found:
            print("未能通过关键字找到 Claude 控件。可能它在 Webview 内部并未暴露文本。")
            print("我们将尝试列出所有 Pane 子窗口，这通常是 WebView 所在的地方。")
            for child in vscode.children(control_type="Pane"):
                print(f"子 Pane: {child.window_text()} | ID: {child.automation_id()}")

    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    list_all_descendants()
