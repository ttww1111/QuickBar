import sys
import time
from pywinauto import Desktop

def inspect():
    print("--- VS Code UI 探测实验 ---")
    print("正在寻找 VS Code 窗口...")
    try:
        # 使用 UIA 后端，这是 Electron 应用（如 VS Code）支持的协议
        windows = Desktop(backend="uia").windows(title_re=".*Visual Studio Code.*")
        if not windows:
            print("错误: 未找到 VS Code 窗口。请确保 VS Code 已打开并显示在屏幕上。")
            return
        
        vscode = windows[0]
        vscode.set_focus() # 尝试激活窗口
        print(f"成功锁定窗口: {vscode.window_text()}")
        print("-" * 30)
        
        print("正在扫描所有 Edit(输入框) 和 Document(文档区域) 控件...")
        print("提示: 如果扫描结果为空，请尝试手动在 Claude 中输入一个字符后再运行。")
        print("-" * 30)

        # 探测 Edit 控件
        edits = vscode.descendants(control_type="Edit")
        if edits:
            print(f"找到 {len(edits)} 个 Edit 控件:")
            for i, child in enumerate(edits):
                try:
                    name = child.window_text() or "无名称"
                    auto_id = child.automation_id() or "无 ID"
                    rect = child.rectangle()
                    print(f"[{i}] 名称: {name}")
                    print(f"    ID: {auto_id}")
                    print(f"    坐标: {rect}")
                except:
                    continue
        else:
            print("未直接找到 Edit 控件。")

        print("-" * 30)
        # 探测 Document 控件 (Claude 的 Webview 通常在这里)
        docs = vscode.descendants(control_type="Document")
        if docs:
            print(f"找到 {len(docs)} 个 Document 控件:")
            for i, child in enumerate(docs):
                try:
                    name = child.window_text() or "无名称"
                    auto_id = child.automation_id() or "无 ID"
                    print(f"[{i}] 名称: {name} | ID: {auto_id}")
                except:
                    continue
        else:
            print("未找到 Document 控件。")

        print("-" * 30)
        print("探测结束。请将上述输出反馈给我。")

    except Exception as e:
        print(f"探测过程中发生异常: {e}")

if __name__ == "__main__":
    inspect()
