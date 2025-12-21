
import pywinauto

def list_all_windows():
    print("正在列出所有可见窗口标题...")
    windows = pywinauto.Desktop(backend="uia").windows()
    for w in windows:
        try:
            title = w.window_text()
            if title:
                print(f"Title: '{title}' | Class: {w.element_info.class_name}")
        except:
            pass

if __name__ == "__main__":
    list_all_windows()
