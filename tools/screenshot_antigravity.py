import tkinter as tk
from PIL import ImageGrab
import os

class ScreenshotTool:
    def __init__(self, filename):
        self.filename = filename
        self.root = tk.Tk()
        self.root.title(f"Capturing: {filename}")
        self.root.attributes('-alpha', 0.3)
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.canvas = tk.Canvas(self.root, cursor="cross", bg="grey")
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

        print(f"--- 截图工具已启动 (目标: {filename}) ---")
        print("操作指引：")
        print("1. 确保 Google Antigravity 对话框在屏幕上可见。")
        print("2. 框选 Antigravity 的特征（如输入框提示语或小图标）。")
        print("3. 按 ESC 退出。")
        self.root.mainloop()

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=2)

    def on_move_press(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        end_x, end_y = event.x, event.y
        x1, x2 = min(self.start_x, end_x), max(self.start_x, end_x)
        y1, y2 = min(self.start_y, end_y), max(self.start_y, end_y)
        
        if x2 - x1 > 5 and y2 - y1 > 5:
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
            img.save(self.filename)
            print(f"成功保存锚点图: {os.path.abspath(self.filename)}")
            self.root.destroy()

if __name__ == "__main__":
    ScreenshotTool("antigravity_anchor.png")
