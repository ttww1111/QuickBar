import tkinter as tk
from tkinter import messagebox, simpledialog
import json
import os
import time
import pyautogui
import pyperclip
import threading
import re
import socket
import sys
from pywinauto import Desktop
from PIL import Image, ImageTk, ImageGrab
try:
    import pystray
    from pystray import MenuItem as item
except ImportError:
    pystray = None

# 版本信息
APP_VERSION = "1.0.0"
GITHUB_REPO = "https://github.com/user/quickbar"  # 替换为实际的仓库地址

def resource_path(relative_path):
    """
    获取资源的绝对路径，兼容 PyInstaller 和 Nuitka 打包模式
    """
    # 1. 尝试 PyInstaller 的 _MEIPASS
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    
    # 2. 尝试 Nuitka 的 __compiled__ 模式
    #    Nuitka onefile 会将数据解压到临时目录，__file__ 指向该目录
    if "__compiled__" in dir():
        # Nuitka 编译后，__file__ 指向 exe 所在的临时解压目录
        base_path = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(base_path, relative_path)
        if os.path.exists(candidate):
            return candidate
    
    # 3. 开发模式：直接使用当前工作目录
    return os.path.join(os.path.abspath("."), relative_path)

# 配置文件路径定义（配置文件不随 exe 打包，放在 exe 同级目录下）
CONFIG_FILE = "config.json"
TARGET_CONFIG_FILE = "target_settings.json"
ASSETS_DIR = resource_path("assets")
ANCHORS_DIR = os.path.join(os.path.abspath("."), "assets", "anchors") # 锚点是运行时生成的



try:
    import win32gui
    import win32ui
    import win32con
    import win32api
except ImportError:
    win32gui = None

class ToolTip:
    """通用的鼠标悬停提示框 (带延迟显示)"""
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_win = None
        self.after_id = None
        # 使用 add="+" 追加事件，避免覆盖已绑定的其他处理器（如颜色切换）
        self.widget.bind("<Enter>", lambda e: self.schedule_tip(), add="+")
        self.widget.bind("<Leave>", lambda e: self.hide_tip(), add="+")


    def schedule_tip(self):
        """计划显示提示"""
        self.hide_tip() # 先确保清除之前的状态
        if self.text:
            self.after_id = self.widget.after(self.delay, self.show_tip)

    def show_tip(self):
        """实际执行显示并在按钮下方弹出，支持自动换行"""
        if self.tip_win or not self.text: return
        
        # 获取宿主 widget 的位置和尺寸
        w_width = self.widget.winfo_width()
        w_height = self.widget.winfo_height()
        x_root = self.widget.winfo_rootx()
        y_root = self.widget.winfo_rooty()
        
        # 获取主窗口的宽度，用于限制 ToolTip 宽度
        app_width = self.widget.winfo_toplevel().winfo_width()
        max_width = max(app_width - 20, 100) # 预留一点边距
        
        self.tip_win = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.attributes("-topmost", True)
        
        # 创建 Label 并强制自动换行
        # wraplength 以像素为单位，设置为 max_width 确保不超宽
        lbl = tk.Label(tw, text=self.text, justify='left', background="#ffffca", 
                       relief='solid', borderwidth=1, font=("Microsoft YaHei", 8),
                       wraplength=max_width)
        lbl.pack()
        
        # 更新 IDLE 以获取真实的 Label 尺寸
        tw.update_idletasks()
        tip_w = tw.winfo_width()
        
        # 计算弹出位置：在 widget 下方，尽量水平居中对齐
        # 如果超出屏幕右侧，Tk 会处理，但我们可以手动校准使其贴合主窗口
        target_x = x_root + (w_width - tip_w) // 2
        target_y = y_root + w_height + 15 # 偏移 15 像素，避免被手型光标遮挡
        
        tw.wm_geometry(f"+{target_x}+{target_y}")


    def hide_tip(self, event=None):
        """隐藏提示并取消定时器"""
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.tip_win:
            self.tip_win.destroy()
            self.tip_win = None


class QuickBarApp:
    """
    QuickBar 主程序类：负责 UI 渲染、自动化逻辑调度、配置持久化及多模式切换
    """
    def __init__(self, root):
        self.root = root
        self.root.title("QuickBar")
        self.root.overrideredirect(True) # 移除原生边框以实现 UI 美化
        self.root.attributes("-alpha", 0.95) # 设置微透明度提升科技感
        
        # 设置窗口图标（任务栏显示）
        try:
            icon_path = os.path.join(ASSETS_DIR, "quickbar_icon.png")
            if os.path.exists(icon_path):
                # 任务栏图标可以稍大一些以便清晰显示
                taskbar_img = ImageTk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, taskbar_img)
                self._app_icon = taskbar_img  # 避免引用被回收
        except Exception as e:
            print(f"Taskbar icon error: {e}")
        
        # 使无边框窗口显示在任务栏
        self.root.after(10, self._show_in_taskbar)

        
        # 1. 加载持久化配置
        self.config_data = self.load_config()
        saved_state = self.config_data.get("state", {})
        
        self._init_variables(saved_state)
        self._init_ui()
        self._bind_events()

    def _init_variables(self, saved_state):
        """初始化运行时的内部变量"""
        # 1. 初始化持久化状态变量
        self.current_ide = tk.StringVar(value=saved_state.get("current_ide", "VS Code"))
        self.current_ai = tk.StringVar(value=saved_state.get("current_ai", "Claude"))
        self.auto_send = tk.BooleanVar(value=saved_state.get("auto_send", True))
        self.is_topmost = tk.BooleanVar(value=saved_state.get("is_topmost", True))
        self.current_theme = tk.StringVar(value=saved_state.get("theme", "Dark")) 
        self.minimize_to = saved_state.get("minimize_to", "taskbar") # 默认任务栏
        self.column_count = tk.StringVar(value=saved_state.get("column_count", "auto")) # "auto", "1", "2"
        self.close_to_tray = tk.BooleanVar(value=saved_state.get("close_to_tray", False))  # 关闭时最小化到托盘
        self.auto_start = tk.BooleanVar(value=saved_state.get("auto_start", False))  # 开机自启
        self.theme_follow_system = tk.BooleanVar(value=saved_state.get("theme_follow_system", True))  # 主题跟随系统
        
        # 如果启用了主题跟随系统，则检测并应用系统主题
        if self.theme_follow_system.get():
            self._apply_system_theme()

        # 3. 基础运行状态
        self.drag_obj = None
        self.drag_start_idx = None
        self.mode = None 
        self.tray_icon = None
        self.placeholder = None
        self.icon_cache = {} 
        self.ui_icons = {}
        self.target_settings = self.load_target_settings()
        self.EDGE_SIZE = 5

        # 4. 国际化支持
        def get_system_lang():
            try:
                import locale
                lang = locale.getlocale()[0] or locale.getdefaultlocale()[0]
                if lang:
                    lang = lang.lower()
                    if 'zh' in lang or 'chinese' in lang: return 'zh'
                    if 'ja' in lang or 'japanese' in lang: return 'ja'
                return 'en'
            except: return 'zh'

        self.language = tk.StringVar(value=saved_state.get("language", get_system_lang()))
        self.translations = {
            "zh": {
                "settings": "全局设置", "column_count": "按钮列数:", "auto": "自动", "single": "单列", "double": "双列",
                "minimize_to": "最小化位置:", "taskbar": "任务栏", "tray": "系统托盘",
                "close_to_tray": "关闭时最小化到托盘", "auto_start": "开机自启动",
                "theme_follow": "主题跟随系统", "language": "界面语言:", "close": "关闭",
                "confirm_delete": "确认删除", "delete_prompt": "是否删除指令", "yes": "是", "no": "否",
                "add_command": "添加新指令", "edit_command": "编辑指令", "name": "名称:", "content": "内容:",
                "save": "保存", "cancel": "取消", "calibration": "输入框校准", "settings_btn": "打开设置",
                "auto_send": "自动发送", "pin": "切换窗口置顶", "show_quickbar": "显示 QuickBar", "exit": "退出",
                "import_config": "导入配置", "export_config": "导出配置", "about": "关于",
                "version": "版本", "check_update": "检查更新", "no_update": "已是最新版本",
                "import_success": "配置导入成功", "export_success": "配置导出成功",
                "calibration_tip": "检测到您尚未校准当前目标的输入框位置。\n\n请先确保已打开目标 IDE 并点开对应的 AI 对话框（使其可见），然后再点击“是”开始校准。是否开始？"
            },
            "en": {
                "settings": "Settings", "column_count": "Columns:", "auto": "Auto", "single": "Single", "double": "Double",
                "minimize_to": "Minimize to:", "taskbar": "Taskbar", "tray": "System Tray",
                "close_to_tray": "Minimize to tray on close", "auto_start": "Start on boot",
                "theme_follow": "Follow system theme", "language": "Language:", "close": "Close",
                "confirm_delete": "Confirm Delete", "delete_prompt": "Delete command", "yes": "Yes", "no": "No",
                "add_command": "Add Command", "edit_command": "Edit Command", "name": "Name:", "content": "Content:",
                "save": "Save", "cancel": "Cancel", "calibration": "Calibrate", "settings_btn": "Settings",
                "auto_send": "Auto Send", "pin": "Toggle Pin", "show_quickbar": "Show QuickBar", "exit": "Exit",
                "import_config": "Import Config", "export_config": "Export Config", "about": "About",
                "version": "Version", "check_update": "Check Update", "no_update": "Already up to date",
                "import_success": "Config imported successfully", "export_success": "Config exported successfully",
                "calibration_tip": "Calibration not detected for this target.\n\nPlease ensure the target IDE and AI chat window are open and visible before clicking 'Yes'. Start calibration now?"
            },
            "ja": {
                "settings": "設定", "column_count": "列数:", "auto": "自動", "single": "1列", "double": "2列",
                "minimize_to": "最小化先:", "taskbar": "タスクバー", "tray": "システムトレイ",
                "close_to_tray": "閉じる時トレイへ", "auto_start": "自動起動",
                "theme_follow": "システムテーマに従う", "language": "言語:", "close": "閉じる",
                "confirm_delete": "削除確認", "delete_prompt": "コマンドを削除", "yes": "はい", "no": "いいえ",
                "add_command": "コマンド追加", "edit_command": "コマンド編集", "name": "名前:", "content": "内容:",
                "save": "保存", "cancel": "キャンセル", "calibration": "キャリブレ", "settings_btn": "設定",
                "auto_send": "自動送信", "pin": "ピン固定", "show_quickbar": "QuickBar表示", "exit": "終了",
                "import_config": "設定インポート", "export_config": "設定エクスポート", "about": "について",
                "version": "バージョン", "check_update": "更新確認", "no_update": "最新版です",
                "import_success": "設定をインポートしました", "export_success": "設定をエクスポートしました",
                "calibration_tip": "現在のターゲットはまだキャリブレーションされていません。\n\nまず対象のIDEとAIチャット画面を開いて表示された状態にしてから、「はい」をクリックして開始してください。開始しますか？"
            }
        }

        # 5. 几何结构与主题
        if "geometry" in saved_state:
            self.root.geometry(saved_state["geometry"])
        else:
            self.root.geometry("200x550+100+100")
        self.root.attributes("-topmost", self.is_topmost.get())
        
        self.themes = {
            "Dark": {
                "bg": "#1e1e1e", "header": "#252526", "btn": "#333333", "btn_hover": "#444444",
                "text": "#cccccc", "text_active": "#ffffff", "subtext": "#858585",
                "active": "#007acc", "accent": "#007acc", "shadow": "#000000"
            },
            "Light": {
                "bg": "#ffffff", "header": "#f3f3f3", "btn": "#eeeeee", "btn_hover": "#e0e0e0",
                "text": "#333333", "text_active": "#000000", "subtext": "#666666",
                "active": "#005a9e", "accent": "#005a9e", "shadow": "#dddddd"
            }
        }
        self.prepare_icons()

    def _init_ui(self):
        """初始 UI 构建"""
        self.setup_ui()
        self.root.after(100, self.auto_adjust_height) 

    def _bind_events(self):
        """绑定全局事件"""
        self.root.bind("<Button-1>", self.on_press)
        self.root.bind("<B1-Motion>", self.on_motion)
        self.root.bind("<Control-q>", lambda e: self.quit_app())
        self.root.bind("<Motion>", self.update_cursor)

    def _show_first_time_tip(self):
        from tkinter import messagebox
        if messagebox.askyesno("QuickBar", self.t("calibration_tip")):
            self.start_calibration()
        # 标记已校准 (或至少已提示)
        self.config_data.setdefault("state", {})["calibrated"] = True
        self.save_config()

    def load_config(self):
        """加载主配置文件，包含指令列表和界面状态"""
        # 获取系统语言用于初始化默认指令
        def get_sys_lang():
            try:
                import locale
                lang = locale.getlocale()[0] or locale.getdefaultlocale()[0]
                if lang:
                    lang = lang.lower()
                    if 'zh' in lang or 'chinese' in lang: return 'zh'
                    if 'ja' in lang or 'japanese' in lang: return 'ja'
                return 'en'
            except: return 'zh'
        
        sys_lang = get_sys_lang()
        
        default_cmds = {
            "zh": [
                {"name": "你好", "text": "你好，请自我介绍一下。"},
                {"name": "写代码", "text": "请帮我写一段 Python 代码实现快速排序。"},
                {"name": "解释代码", "text": "请解释一下这段代码的逻辑。"},
                {"name": "找 Bug", "text": "请帮我检查一下这段代码是否存在潜在的 Bug。"}
            ],
            "en": [
                {"name": "Hello", "text": "Hello, please introduce yourself."},
                {"name": "Write Code", "text": "Please help me write a Python code for Quicksort."},
                {"name": "Explain", "text": "Please explain the logic of this code."},
                {"name": "Find Bug", "text": "Please help me check if there are any potential bugs in this code."}
            ],
            "ja": [
                {"name": "こんにちは", "text": "こんにちは、自己紹介をお願いします。"},
                {"name": "コード作成", "text": "クイックソートを実装するPythonコードを書いてください。"},
                {"name": "コード解説", "text": "このコードのロジックを説明してください。"},
                {"name": "バグ修正", "text": "このコードに潜在的なバグがないか確認してください。"}
            ]
        }
        
        default_data = {
            "commands": default_cmds.get(sys_lang, default_cmds["en"]),
            "state": {}
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list): return {"commands": data, "state": {}}
                    return data
            except: pass
        return default_data

    @property
    def commands(self): return self.config_data.setdefault("commands", [])

    def save_config(self):
        """保存当前所有 UI 状态和窗口几何至磁盘"""
        self.config_data["state"] = {
            "current_ide": self.current_ide.get(),
            "current_ai": self.current_ai.get(),
            "auto_send": self.auto_send.get(),
            "is_topmost": self.is_topmost.get(),
            "theme": self.current_theme.get(),
            "minimize_to": self.minimize_to,
            "column_count": self.column_count.get(),
            "close_to_tray": self.close_to_tray.get(),
            "auto_start": self.auto_start.get(),
            "theme_follow_system": self.theme_follow_system.get(),
            "language": getattr(self, 'language', tk.StringVar(value="zh")).get(),
            "geometry": self.root.geometry(),
            "calibrated": self.config_data.get("state", {}).get("calibrated", False)
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=4)


    def load_target_settings(self):
        """加载各个自动化目标的识别锚点及点击偏移位置"""
        default = {
            "VS Code": {
                "Claude": {"image": os.path.join(ANCHORS_DIR, "vscode_claude.png"), "offset_x": 0, "offset_y": -45, "win_title": ".*(Visual Studio Code|VS Code).*"},
                "Codex": {"image": os.path.join(ANCHORS_DIR, "vscode_codex.png"), "offset_x": 0, "offset_y": -45, "win_title": ".*(Visual Studio Code|VS Code).*"}
            },
            "Antigravity": {
                "Antigravity": {"image": os.path.join(ANCHORS_DIR, "anti_anti.png"), "offset_x": 0, "offset_y": 200, "win_title": ".*(Visual Studio Code|VS Code|QuickBar - Antigravity).*"},
                "Claude": {"image": os.path.join(ANCHORS_DIR, "anti_claude.png"), "offset_x": 0, "offset_y": -45, "win_title": ".*(Visual Studio Code|VS Code|QuickBar - Antigravity).*"},
                "Codex": {"image": os.path.join(ANCHORS_DIR, "anti_codex.png"), "offset_x": 0, "offset_y": -45, "win_title": ".*(Visual Studio Code|VS Code|QuickBar - Antigravity).*"}
            },
            "Native CLI": {
                "Terminal": {
                    "image": os.path.join(ANCHORS_DIR, "cli_anchor.png"), 
                    "win_title": "^(?!.*(Claude|Codex)).*(PowerShell|CMD|Terminal|管理员|cmd.exe|powershell.exe).*"
                }
            }
        }
        if os.path.exists(TARGET_CONFIG_FILE):
            try:
                with open(TARGET_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "VS Code" in data: return data
            except: pass
        return default

    def t(self, key):
        """获取当前语言的翻译文本"""
        lang = self.language.get()
        return self.translations.get(lang, self.translations["zh"]).get(key, key)

    def _apply_system_theme(self):
        """检测并应用系统主题"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            self.current_theme.set("Light" if value == 1 else "Dark")
        except:
            pass  # 无法检测时保持当前主题

    def _set_auto_start(self, enable):
        """设置开机自启动"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enable:
                import sys
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, "QuickBar", 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, "QuickBar")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"设置开机自启失败: {e}")

    def set_ide(self, ide):
        """切换目标 IDE 容器"""
        self.current_ide.set(ide)
        available_ais = list(self.target_settings[ide].keys())
        self.current_ai.set(available_ais[0]) # 切换 IDE 时默认选中第一个附属 AI
        self.save_config(); self.setup_ui()

    def set_ai(self, ai):
        """切换具体 AI 目标"""
        self.current_ai.set(ai); self.save_config(); self.setup_ui()

    def toggle_theme(self):
        """在 Dark/Light 两种主题间一键切换"""
        new_theme = "Light" if self.current_theme.get() == "Dark" else "Dark"
        self.current_theme.set(new_theme)
        self.save_config(); self.setup_ui()

    def quit_app(self):
        """关闭程序：根据设置决定退出或最小化到托盘"""
        if self.close_to_tray.get():
            # 最小化到托盘而不是退出
            self.root.withdraw()
            if not self.tray_icon:
                import threading
                threading.Thread(target=self.setup_tray, daemon=True).start()
        else:
            # 彻底退出
            if self.tray_icon:
                self.tray_icon.stop()
            # 确保在退出前销毁所有窗口
            self.root.quit()
            self.root.destroy()
            sys.exit(0)

    def force_quit(self):
        """强制退出程序（托盘菜单使用）"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

    def _show_in_taskbar(self):
        """使无边框窗口显示在任务栏中，并支持任务栏点击最小化"""
        try:
            import ctypes
            
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd == 0:
                hwnd = self.root.winfo_id()
            
            # 保存窗口句柄供后续使用
            self.hwnd = hwnd
            
            # 获取当前样式
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            # 移除工具窗口样式，添加应用窗口样式
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            
            # 刷新窗口
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)
                
        except Exception as e:
            print(f"任务栏显示设置失败: {e}")


    def minimize_app(self, event=None):
        """处理最小化逻辑：首次弹出询问"""
        if self.minimize_to is None:
            # 首次询问弹窗
            dialog = tk.Toplevel(self.root)
            dialog.title("最小化偏好设置")
            dialog.geometry(f"300x150+{self.root.winfo_x()-50}+{self.root.winfo_y()+150}")
            dialog.attributes("-topmost", True)
            colors = self.themes[self.current_theme.get()]
            dialog.configure(bg=colors["bg"])
            
            tk.Label(dialog, text="请选择默认最小化行为:", bg=colors["bg"], fg=colors["text"], font=("Microsoft YaHei", 9)).pack(pady=20)
            
            f = tk.Frame(dialog, bg=colors["bg"])
            f.pack(fill="x", padx=10)
            
            def set_choice(choice):
                self.minimize_to = choice
                self.save_config()
                dialog.destroy()
                self._execute_minimize()
                
            tk.Button(f, text="任务栏", bg=colors["btn"], fg=colors["text"], command=lambda: set_choice("taskbar"), relief="flat", width=10).pack(side="left", expand=True)
            tk.Button(f, text="系统托盘", bg=colors["btn"], fg=colors["text"], command=lambda: set_choice("tray"), relief="flat", width=10).pack(side="left", expand=True)
        else:
            self._execute_minimize()
        return "break"

    def _execute_minimize(self):
        if self.minimize_to == "tray":
            self.root.withdraw()
            if not self.tray_icon:
                threading.Thread(target=self.setup_tray, daemon=True).start()
        else:
            self.root.iconify()

    def show_window(self):
        """从托盘恢复窗口"""
        self.root.deiconify()
        self.root.attributes("-topmost", self.is_topmost.get())
        self.save_config()

    def prepare_icons(self):
        """
        初始化图标状态并建立全局缓存。
        """
        self.icon_cache = {} 
        icons_to_load = {
            "app": "quickbar_icon.png",
            "vscode": "Vscode.png",
            "antigravity": "Antigravity.png",
            "terminal": "terminal_icon.png",
            "claude": "Claude.png",
            "codex": "Codex.png"
        }
        
        for key, name in icons_to_load.items():
            path = os.path.join(ASSETS_DIR, name)
            if os.path.exists(path):
                try:
                    # 预先把图像加载进内存
                    self.icon_cache[key] = Image.open(path).convert("RGBA")
                except Exception as e:
                    print(f"Error loading icon {name}: {e}")
            else:
                print(f"警告: 关键图标文件丢失 -> {name} (路径: {path})")

    def setup_tray(self):
        """设置并运行系统托盘"""
        if not pystray: return
        
        # 使用 QuickBar 专属图标（增大尺寸以获得更清晰的显示）
        try:
            image = Image.open(os.path.join(ASSETS_DIR, "quickbar_icon.png")).resize((128, 128), Image.LANCZOS)
        except:
            image = Image.new('RGB', (128, 128), color=(0, 122, 204))
        
        def on_double_click(icon, item):
            """双击托盘图标时显示窗口"""
            self.show_window()
            
        menu = pystray.Menu(
            item(self.t('show_quickbar'), self.show_window, default=True),
            item(self.t('exit'), self.force_quit)
        )
        self.tray_icon = pystray.Icon("QuickBar", image, "QuickBar", menu)
        self.tray_icon.run()



    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        points = [x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y1+radius, x2, y2-radius, x2, y2-radius, x2, y2, x2-radius, y2, x2-radius, y2, x1+radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

    def setup_ui(self):
        """重绘主界面 UI 组件"""
        for widget in self.root.winfo_children(): widget.destroy()
        colors = self.themes[self.current_theme.get()]
        self.root.configure(bg=colors["bg"])

        # 构建头部区域 (标题栏)
        header = tk.Frame(self.root, bg=colors["header"], height=26)
        header.pack(fill="x")
        header.pack_propagate(False)

        # 左侧：软件图标 + 标题
        left_frame = tk.Frame(header, bg=colors["header"])
        left_frame.pack(side="left", fill="y")
        
        # 加载并显示软件图标
        try:
            if "app" in self.icon_cache:
                img = self.icon_cache["app"].resize((12, 12), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                icon_lbl = tk.Label(left_frame, image=photo, bg=colors["header"])
                icon_lbl.image = photo 
                icon_lbl.pack(side="left", padx=(6, 2)) 
        except Exception as e:
            print(f"Title icon error: {e}")
        
        tk.Label(left_frame, text="QuickBar", bg=colors["header"], fg=colors["subtext"], 
                font=("Segoe UI", 8, "bold")).pack(side="left", padx=(1, 0))

        
        # 右侧操作按钮容器
        btn_frame = tk.Frame(header, bg=colors["header"])
        btn_frame.pack(side="right", fill="y")

        # 1. 关闭按钮
        btn_close = tk.Label(btn_frame, text="×", bg=colors["header"], fg=colors["subtext"], 
                            font=("Segoe UI", 11), cursor="hand2", width=3)
        btn_close.pack(side="right", fill="y")
        btn_close.bind("<Button-1>", lambda e: [self.quit_app(), "break"][-1])
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg="#e81123", fg="white"))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=colors["header"], fg=colors["subtext"]))

        # 2. 最小化按钮
        btn_min = tk.Label(btn_frame, text="—", bg=colors["header"], fg=colors["subtext"], 
                          font=("Segoe UI", 7), cursor="hand2", width=3)
        btn_min.pack(side="right", fill="y")
        btn_min.bind("<Button-1>", self.minimize_app)
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg=colors["btn_hover"]))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=colors["header"]))

        # 3. 主题切换按钮
        theme_canvas = tk.Canvas(btn_frame, bg=colors["header"], width=24, height=26, highlightthickness=0, cursor="hand2")
        theme_canvas.pack(side="right", fill="y")
        theme_icon = "\uE708" if self.current_theme.get() == "Dark" else "\uE706"
        theme_canvas.create_text(12, 13, text=theme_icon, fill=colors["subtext"], font=("Segoe MDL2 Assets", 9), anchor="center")
        
        def on_theme_enter(e): theme_canvas.configure(bg=colors["btn_hover"])
        def on_theme_leave(e): theme_canvas.configure(bg=colors["header"])
        theme_canvas.bind("<Enter>", on_theme_enter)
        theme_canvas.bind("<Leave>", on_theme_leave)
        theme_canvas.bind("<Button-1>", lambda e: [self.toggle_theme(), "break"][-1])

        # 4. 置顶按钮
        top_canvas = tk.Canvas(btn_frame, bg=colors["header"], width=24, height=26, highlightthickness=0, cursor="hand2")
        top_canvas.pack(side="right", fill="y")
        
        is_pinned = self.is_topmost.get()
        top_icon = "\uE840" if is_pinned else "\uE718"
        top_color = colors["active"] if is_pinned else colors["subtext"]
        
        # 居中显示图标 (width=24, 中心点=12)
        top_canvas.create_text(12, 13, text=top_icon, fill=top_color, font=("Segoe MDL2 Assets", 9), anchor="center")
        
        def on_top_enter(e): top_canvas.configure(bg=colors["btn_hover"])
        def on_top_leave(e): top_canvas.configure(bg=colors["header"])
        top_canvas.bind("<Enter>", on_top_enter)
        top_canvas.bind("<Leave>", on_top_leave)
        def toggle_top(e):
            self.is_topmost.set(not self.is_topmost.get())
            self.root.attributes("-topmost", self.is_topmost.get())
            self.save_config()
            self.setup_ui()
            return "break"
        top_canvas.bind("<Button-1>", toggle_top)
        ToolTip(top_canvas, "切换窗口置顶")


        # 1. 顶部模式选择区 (图标化切换)
        top_frame = tk.Frame(self.root, bg=colors["bg"])
        top_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # IDE 切换
        ide_scroll = tk.Frame(top_frame, bg=colors["bg"])
        ide_scroll.pack(fill="x")
        
        # 将显示用图标存入 cache 以免 GC
        self.ui_icons = {}
        
        ide_map = {
            "VS Code": "vscode",
            "Antigravity": "antigravity",
            "Native CLI": "terminal"
        }

        for ide, cache_key in ide_map.items():
            is_active = (self.current_ide.get() == ide)
            f = tk.Frame(ide_scroll, bg=colors["header"],
                         highlightbackground=colors["active"] if is_active else colors["header"],
                         highlightthickness=1, bd=0, cursor="hand2")


            f.pack(side="left", expand=True, fill="x", padx=2)

            
            # 尝试加载图标
            try:
                if cache_key in self.icon_cache:
                    # 从内存缓存获取基础图像
                    img = self.icon_cache[cache_key].copy()
                    img = img.resize((16, 16), Image.LANCZOS)
                    
                    # 动态处理
                    if ide == "Native CLI" and self.current_theme.get() == "Light":
                        pixels = img.load()
                        for y in range(img.height):
                            for x in range(img.width):
                                r, g, b, a = pixels[x, y]
                                if r > 200 and g > 200 and b > 200 and a > 100:
                                    pixels[x, y] = (80, 80, 80, a)
                    
                    photo = ImageTk.PhotoImage(img)
                    self.ui_icons[ide] = photo
                    lbl = tk.Label(f, image=photo, bg=colors["header"], cursor="hand2", padx=6, pady=4)

                else:
                    lbl = tk.Label(f, text=ide[:2], bg=colors["header"], 
                                  fg=colors["text_active"] if is_active else colors["subtext"], 
                                  font=("Segoe UI", 9, "bold"), cursor="hand2")
            except:
                lbl = tk.Label(f, text=ide[:2], bg=colors["header"], 
                              fg=colors["text_active"] if is_active else colors["subtext"], 
                              font=("Segoe UI", 9, "bold"), cursor="hand2")
            
            lbl.pack(fill="x")



            # 将点击事件绑定到 Frame 和 Label，确保整个区域可点
            for widget in (f, lbl):
                widget.bind("<Button-1>", lambda e, i=ide: [self.set_ide(i), "break"][-1])
                ToolTip(widget, ide) # 同时为 Frame 和 Label 绑定 ToolTip




        # AI 切换
        if self.current_ide.get() != "Native CLI":
            ai_frame = tk.Frame(self.root, bg=colors["bg"])
            ai_frame.pack(fill="x", padx=10, pady=2)
            
            # AI 图标映射
            ai_icon_files = {
                "Claude": os.path.join(ASSETS_DIR, "Claude.png"),
                "Codex": os.path.join(ASSETS_DIR, "Codex.png"),
                "Antigravity": os.path.join(ASSETS_DIR, "Antigravity.png")
            }

            for ai in self.target_settings[self.current_ide.get()].keys():
                is_active = (self.current_ai.get() == ai)
                # 使用 Frame 包装以实现边框效果
                af = tk.Frame(ai_frame, bg=colors["header"], 
                              highlightbackground=colors["active"] if is_active else colors["header"],
                              highlightthickness=1, bd=0, cursor="hand2")
                af.pack(side="left", expand=True, fill="x", padx=2)
                
                # 尝试加载 AI 图标
                ai_key = ai.lower()
                if ai_key in self.icon_cache:
                    try:
                        ai_img = self.icon_cache[ai_key].copy().resize((16, 16), Image.LANCZOS)
                        
                        if ai == "Codex" and self.current_theme.get() == "Dark":
                            pixels = ai_img.load()
                            for y in range(ai_img.height):
                                for x in range(ai_img.width):
                                    r, g, b, a = pixels[x, y]
                                    if r < 100 and g < 100 and b < 100 and a > 100:
                                        pixels[x, y] = (200, 200, 200, a)
                        
                        ai_photo = ImageTk.PhotoImage(ai_img)
                        self.ui_icons[f"ai_{ai}"] = ai_photo
                        b = tk.Label(af, image=ai_photo, bg=colors["header"], cursor="hand2", padx=6, pady=4)
                    except:
                        b = tk.Label(af, text=ai, bg=colors["header"], 
                                    fg=colors["text_active"] if is_active else colors["subtext"], 
                                    font=("Segoe UI", 7, "bold" if is_active else "normal"),
                                    padx=8, pady=4, cursor="hand2")
                else:
                    b = tk.Label(af, text=ai, bg=colors["header"], 
                                fg=colors["text_active"] if is_active else colors["subtext"], 
                                font=("Segoe UI", 7, "bold" if is_active else "normal"),
                                padx=6, pady=2, cursor="hand2")

                b.pack(fill="x")
                # 为 Frame 和 Label 同时绑定点击和 ToolTip
                for widget in (af, b):
                    widget.bind("<Button-1>", lambda e, i=ai: [self.set_ai(i), "break"][-1])
                    ToolTip(widget, ai)





        # 2. 中间指令列表区 (取消 expand，方便高度自适应)
        self.cmd_container = tk.Frame(self.root, bg=colors["bg"])
        self.cmd_container.pack(fill="x", expand=False, pady=5, padx=10)
        self.refresh_cmd_list()


        # 3. 底部集成工具栏 (重新排列：自动发送 → 加号 → 校准 → 设置)
        footer = tk.Frame(self.root, bg=colors["header"])
        footer.pack(fill="x", side="bottom")

        # 1. 自动发送组 (最左侧)
        auto_frame = tk.Frame(footer, bg=colors["header"])
        auto_frame.pack(side="left", padx=(5, 0))
        
        is_auto = self.auto_send.get()
        check_icon = "\uE73E" if is_auto else "\uE739"
        check_color = colors["active"] if is_auto else colors["subtext"]
        
        check_box = tk.Label(auto_frame, text=check_icon, bg=colors["header"], fg=check_color,
                            font=("Segoe MDL2 Assets", 10), cursor="hand2", pady=5)
        check_box.pack(side="left")
        
        auto_lbl = tk.Label(auto_frame, text="自动发送", bg=colors["header"], fg=colors["subtext"], 
                 font=("Microsoft YaHei", 8), cursor="hand2", pady=5)
        auto_lbl.pack(side="left", padx=(2, 0))
        
        def toggle_auto(e=None):
            self.auto_send.set(not self.auto_send.get())
            self.save_config()
            # 只刷新复选框图标，避免重建整个UI导致闪动
            new_icon = "\uE73E" if self.auto_send.get() else "\uE739"
            new_color = colors["active"] if self.auto_send.get() else colors["subtext"]
            check_box.config(text=new_icon, fg=new_color)
            return "break"
        
        def on_auto_enter(e, lbl=auto_lbl, cb=check_box, c=colors):
            lbl.config(fg=c["active"])
            cb.config(fg=c["active"])
            
        def on_auto_leave(e, lbl=auto_lbl, cb=check_box, c=colors, cc=check_color):
            lbl.config(fg=c["subtext"])
            cb.config(fg=cc)

        for w in (check_box, auto_lbl):
            w.bind("<Button-1>", toggle_auto)
            w.bind("<Enter>", on_auto_enter)
            w.bind("<Leave>", on_auto_leave)

        # 底部右侧按钮（按照加号、校准、设置的顺序从左到右）
        # 由于使用 side="right"uff0c需要反向声明
        
        # 4. 设置按钮（最右）
        set_btn = tk.Label(footer, text="\uE713", bg=colors["header"], fg=colors["subtext"],
                          font=("Segoe MDL2 Assets", 9), cursor="hand2", padx=4, pady=5)
        set_btn.pack(side="right", padx=(0, 2))
        set_btn.bind("<Button-1>", lambda e: [self.open_settings(), "break"][-1])
        set_btn.bind("<Enter>", lambda e, w=set_btn: w.config(fg=colors["active"]))
        set_btn.bind("<Leave>", lambda e, w=set_btn: w.config(fg=colors["subtext"]))
        ToolTip(set_btn, "打开设置")

        # 3. 校准按钮（中间）
        cal_btn = tk.Label(footer, text="\uE81D", bg=colors["header"], fg=colors["subtext"],
                          font=("Segoe MDL2 Assets", 9), cursor="hand2", padx=4, pady=5)
        cal_btn.pack(side="right", padx=(0, 2))
        cal_btn.bind("<Button-1>", lambda e: [self.start_calibration(), "break"][-1])
        cal_btn.bind("<Enter>", lambda e, w=cal_btn: w.config(fg=colors["active"]))
        cal_btn.bind("<Leave>", lambda e, w=cal_btn: w.config(fg=colors["subtext"]))
        ToolTip(cal_btn, "输入框校准")

        # 2. 加号按钮（最左）
        add_btn = tk.Label(footer, text="\uE710", bg=colors["header"], fg=colors["subtext"], 
                          font=("Segoe MDL2 Assets", 9), cursor="hand2", padx=4, pady=5)
        add_btn.pack(side="right", padx=(0, 2))
        add_btn.bind("<Button-1>", lambda e: [self.add_command_dialog(), "break"][-1])
        add_btn.bind("<Enter>", lambda e, w=add_btn: w.config(fg=colors["active"]))
        add_btn.bind("<Leave>", lambda e, w=add_btn: w.config(fg=colors["subtext"]))
        ToolTip(add_btn, "添加新指令")
        
        self.auto_adjust_height()


    def open_settings(self):
        """打开全局设置面板"""
        colors = self.themes[self.current_theme.get()]
        win = tk.Toplevel(self.root)
        win.title("QuickBar " + self.t("settings"))
        
        # 智能计算设置窗口位置，防止超出屏幕边缘
        set_w, set_h = 300, 420
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        
        # 初始偏置位置
        target_x = self.root.winfo_x() + 20
        target_y = self.root.winfo_y() + 30
        
        # 如果右侧超出屏幕，则向左偏移
        if target_x + set_w > screen_w:
            target_x = self.root.winfo_x() - set_w - 5
            
        # 如果底部超出屏幕，则向上偏移
        if target_y + set_h > screen_h:
            target_y = screen_h - set_h - 40
            
        # 确保不会超出左侧和顶部边缘
        target_x = max(0, target_x)
        target_y = max(0, target_y)
        
        win.geometry(f"{set_w}x{set_h}+{target_x}+{target_y}")
        win.configure(bg=colors["bg"])
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="⚙️ " + self.t("settings"), bg=colors["bg"], fg=colors["active"], 
                font=("Microsoft YaHei", 10, "bold")).pack(pady=10)

        # 选项：指令按钮列数
        f_col = tk.Frame(win, bg=colors["bg"])
        f_col.pack(fill="x", padx=15, pady=6)
        tk.Label(f_col, text=self.t("column_count"), bg=colors["bg"], fg=colors["text"], 
                font=("Microsoft YaHei", 9)).pack(side="left")
        
        col_options = [("auto", self.t("auto")), ("1", self.t("single")), ("2", self.t("double"))]
        col_frame = tk.Frame(f_col, bg=colors["bg"])
        col_frame.pack(side="right")
        
        def on_col_change(val):
            self.column_count.set(val)
            self.save_config()
            self.setup_ui()
        
        for val, label in col_options:
            is_selected = self.column_count.get() == val
            btn = tk.Label(col_frame, text=label, 
                          bg=colors["active"] if is_selected else colors["btn"],
                          fg="white" if is_selected else colors["text"], 
                          font=("Microsoft YaHei", 8), padx=6, pady=2, cursor="hand2")
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, v=val: [on_col_change(v), win.destroy()])

        # 选项：最小化位置
        f1 = tk.Frame(win, bg=colors["bg"])
        f1.pack(fill="x", padx=15, pady=6)
        tk.Label(f1, text=self.t("minimize_to"), bg=colors["bg"], fg=colors["text"], 
                font=("Microsoft YaHei", 9)).pack(side="left")
        
        min_options = [("taskbar", self.t("taskbar")), ("tray", self.t("tray"))]
        min_frame = tk.Frame(f1, bg=colors["bg"])
        min_frame.pack(side="right")
        
        def on_min_change(val):
            self.minimize_to = val
            self.save_config()
        
        for val, label in min_options:
            is_selected = self.minimize_to == val
            btn = tk.Label(min_frame, text=label, 
                          bg=colors["active"] if is_selected else colors["btn"],
                          fg="white" if is_selected else colors["text"], 
                          font=("Microsoft YaHei", 8), padx=8, pady=2, cursor="hand2")
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, v=val: [on_min_change(v), win.destroy(), self.setup_ui()])

        # 选项：关闭时最小化到托盘
        f_close = tk.Frame(win, bg=colors["bg"])
        f_close.pack(fill="x", padx=15, pady=6)
        close_var = self.close_to_tray
        def toggle_close():
            close_var.set(not close_var.get())
            self.save_config()
        close_cb = tk.Checkbutton(f_close, text=self.t("close_to_tray"), variable=close_var,
                                  bg=colors["bg"], fg=colors["text"], selectcolor=colors["header"],
                                  activebackground=colors["bg"], activeforeground=colors["text"],
                                  font=("Microsoft YaHei", 9), command=lambda: self.save_config())
        close_cb.pack(side="left")

        # 选项：开机自启动
        f_auto = tk.Frame(win, bg=colors["bg"])
        f_auto.pack(fill="x", padx=15, pady=6)
        auto_var = self.auto_start
        def toggle_auto_start():
            self._set_auto_start(auto_var.get())
            self.save_config()
        auto_cb = tk.Checkbutton(f_auto, text=self.t("auto_start"), variable=auto_var,
                                 bg=colors["bg"], fg=colors["text"], selectcolor=colors["header"],
                                 activebackground=colors["bg"], activeforeground=colors["text"],
                                 font=("Microsoft YaHei", 9), command=toggle_auto_start)
        auto_cb.pack(side="left")

        # 选项：主题跟随系统
        f_theme = tk.Frame(win, bg=colors["bg"])
        f_theme.pack(fill="x", padx=15, pady=6)
        theme_var = self.theme_follow_system
        def toggle_theme_follow():
            if theme_var.get():
                self._apply_system_theme()
                self.setup_ui()
            self.save_config()
        theme_cb = tk.Checkbutton(f_theme, text=self.t("theme_follow"), variable=theme_var,
                                  bg=colors["bg"], fg=colors["text"], selectcolor=colors["header"],
                                  activebackground=colors["bg"], activeforeground=colors["text"],
                                  font=("Microsoft YaHei", 9), command=toggle_theme_follow)
        theme_cb.pack(side="left")

        # 选项：界面语言
        f_lang = tk.Frame(win, bg=colors["bg"])
        f_lang.pack(fill="x", padx=15, pady=6)
        tk.Label(f_lang, text=self.t("language"), bg=colors["bg"], fg=colors["text"], 
                font=("Microsoft YaHei", 9)).pack(side="left")
        
        lang_options = [("zh", "中文"), ("en", "English"), ("ja", "日本語")]
        lang_frame = tk.Frame(f_lang, bg=colors["bg"])
        lang_frame.pack(side="right")
        
        def on_lang_change(val):
            self.language.set(val)
            self.save_config()
            win.destroy()
            self.setup_ui()
        
        for val, label in lang_options:
            is_selected = self.language.get() == val
            btn = tk.Label(lang_frame, text=label, 
                          bg=colors["active"] if is_selected else colors["btn"],
                          fg="white" if is_selected else colors["text"], 
                          font=("Microsoft YaHei", 8), padx=6, pady=2, cursor="hand2")
            btn.pack(side="left", padx=2)
            btn.bind("<Button-1>", lambda e, v=val: on_lang_change(v))

        # 分隔线
        tk.Frame(win, bg=colors["subtext"], height=1).pack(fill="x", padx=15, pady=10)

        # 配置导入导出按钮
        f_config = tk.Frame(win, bg=colors["bg"])
        f_config.pack(fill="x", padx=15, pady=6)
        
        def import_config():
            from tkinter import filedialog, messagebox
            file_path = filedialog.askopenfilename(
                title=self.t("import_config"),
                filetypes=[("JSON", "*.json")],
                initialdir=os.path.dirname(os.path.abspath(__file__))
            )
            if file_path:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        imported = json.load(f)
                    self.config_data = imported
                    self.save_config()
                    messagebox.showinfo("QuickBar", self.t("import_success"))
                    win.destroy()
                    self.setup_ui()
                except Exception as e:
                    messagebox.showerror("Error", str(e))
        
        def export_config():
            from tkinter import filedialog, messagebox
            file_path = filedialog.asksaveasfilename(
                title=self.t("export_config"),
                defaultextension=".json",
                filetypes=[("JSON", "*.json")],
                initialfile="quickbar_config_backup.json"
            )
            if file_path:
                try:
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(self.config_data, f, ensure_ascii=False, indent=4)
                    messagebox.showinfo("QuickBar", self.t("export_success"))
                except Exception as e:
                    messagebox.showerror("Error", str(e))
        
        tk.Button(f_config, text=self.t("import_config"), bg=colors["btn"], fg=colors["text"],
                 relief="flat", font=("Microsoft YaHei", 8), command=import_config).pack(side="left", padx=5)
        tk.Button(f_config, text=self.t("export_config"), bg=colors["btn"], fg=colors["text"],
                 relief="flat", font=("Microsoft YaHei", 8), command=export_config).pack(side="left", padx=5)

        # 底部：版本信息和检查更新
        bottom_frame = tk.Frame(win, bg=colors["bg"])
        bottom_frame.pack(side="bottom", fill="x", pady=5, padx=15)
        
        # 在版本文字前显示图标
        try:
            if "app" in self.icon_cache:
                s_img = self.icon_cache["app"].copy().resize((14, 14), Image.LANCZOS)
                s_photo = ImageTk.PhotoImage(s_img)
                s_lbl = tk.Label(bottom_frame, image=s_photo, bg=colors["bg"])
                s_lbl.image = s_photo
                s_lbl.pack(side="left", padx=(0, 5))
        except: pass

        tk.Label(bottom_frame, text=f"QuickBar v{APP_VERSION}", bg=colors["bg"], fg=colors["subtext"], 
                font=("Segoe UI", 8)).pack(side="left")
        
        def check_update():
            from tkinter import messagebox
            try:
                import urllib.request
                # 尝试从 GitHub API 获取最新版本（需要替换为实际仓库地址）
                # url = f"{GITHUB_REPO}/releases/latest"
                # 目前显示占位信息
                messagebox.showinfo("QuickBar", self.t("no_update"))
            except:
                messagebox.showinfo("QuickBar", self.t("no_update"))
        
        update_btn = tk.Label(bottom_frame, text=self.t("check_update"), bg=colors["bg"], 
                             fg=colors["active"], font=("Microsoft YaHei", 8), cursor="hand2")
        update_btn.pack(side="right")
        update_btn.bind("<Button-1>", lambda e: check_update())
        update_btn.bind("<Enter>", lambda e: update_btn.config(font=("Microsoft YaHei", 8, "underline")))
        update_btn.bind("<Leave>", lambda e: update_btn.config(font=("Microsoft YaHei", 8)))


    def refresh_cmd_list(self):
        """刷新指令按钮列表并绑定交互事件 (Canvas 绘制圆角，支持自适应)"""
        for widget in self.cmd_container.winfo_children(): widget.destroy()
        colors = self.themes[self.current_theme.get()]
        
        # 根据设置决定列数
        col_setting = self.column_count.get()
        if col_setting == "auto":
            # 自动模式：超过 10 个用双列
            num_columns = 2 if len(self.commands) > 10 else 1
        else:
            num_columns = int(col_setting)
        
        # 预创建一个占位符
        self.placeholder = tk.Canvas(self.cmd_container, bg=colors["bg"], height=40, highlightthickness=0)
        
        def draw_placeholder(e):
            self.placeholder.delete("all")
            w = self.placeholder.winfo_width()
            if w > 10:
                self._draw_rounded_rect(self.placeholder, 2, 2, w-4, 38, radius=8, fill=colors["header"], outline=colors["active"], width=1)
        self.placeholder.bind("<Configure>", draw_placeholder)
        
        # 配置 grid 列权重
        for col in range(num_columns):
            self.cmd_container.columnconfigure(col, weight=1)
        else:
            self.cmd_container.columnconfigure(0, weight=1)
        
        for idx, cmd in enumerate(self.commands):
            # 计算行列位置
            row = idx // num_columns
            col = idx % num_columns
            
            btn_canvas = tk.Canvas(self.cmd_container, bg=colors["bg"], height=38, highlightthickness=0, cursor="hand2")
            
            if num_columns > 1:
                btn_canvas.grid(row=row, column=col, sticky="ew", pady=2, padx=2)
            else:
                btn_canvas.grid(row=row, column=0, sticky="ew", pady=2)
            
            # 使用列表存储 ID 以便在 resize 时更新
            refs = {"rect": None, "text": None}
            
            def draw_btn(e, c=btn_canvas, name=cmd['name'], r=refs):
                c.delete("all")
                w = e.width
                if w > 10:
                    # 绘制带边框的圆角矩形，初始边框与背景同色（透明效果）
                    r["rect"] = self._draw_rounded_rect(c, 2, 2, w-4, 32, radius=6, fill=colors["btn"], outline=colors["btn"])
                    r["text"] = c.create_text(w/2, 17, text=name, fill=colors["text"], font=("Microsoft YaHei", 9))

            btn_canvas.bind("<Configure>", draw_btn)
            
            # 悬停动效（含边框颜色变化）
            def on_enter(e, c=btn_canvas, r=refs):
                if r["rect"]: 
                    c.itemconfigure(r["rect"], fill=colors["btn_hover"], outline=colors["active"])
                if r["text"]: 
                    c.itemconfigure(r["text"], fill=colors["text_active"])
                
            def on_leave(e, c=btn_canvas, r=refs):
                if r["rect"]: 
                    c.itemconfigure(r["rect"], fill=colors["btn"], outline=colors["btn"])
                if r["text"]: 
                    c.itemconfigure(r["text"], fill=colors["text"])

            btn_canvas.bind("<Enter>", on_enter)
            btn_canvas.bind("<Leave>", on_leave)

            
            # 绑定拖拽逻辑
            btn_canvas.bind("<Button-1>", lambda e, i=idx, t=cmd['text']: self.start_drag(e, i, t))
            btn_canvas.bind("<B1-Motion>", self.do_drag)
            btn_canvas.bind("<ButtonRelease-1>", self.stop_drag)
            btn_canvas.bind("<Button-3>", lambda e, c=cmd, i=idx: self.show_context_menu(e, c, i))

            
            ToolTip(btn_canvas, cmd['text'])


    # --- 改进后的拖拽排序逻辑（带虚线占位符） ---
    def start_drag(self, event, idx, text):
        """按下按钮：初始化拖拽环境，并在此处检查校准"""
        # 检查当前选中的目标(IDE + AI)是否已校准
        ide, ai = self.current_ide.get(), self.current_ai.get()
        config = self.target_settings.get(ide, {}).get(ai, {})
        is_calibrated = config.get("offset_x", 0) != 0 or config.get("offset_y", 0) != 0
        
        # Native CLI 模式不需要校准提示（使用的是右键粘贴逻辑）
        if ide != "Native CLI" and not is_calibrated:
            from tkinter import messagebox
            if messagebox.askyesno("QuickBar", self.t("calibration_tip")):
                self.start_calibration()
                return "break"

        self.drag_start_idx = idx
        self.drag_text = text
        self.drag_obj = event.widget
        self.drag_y_origin = event.y 
        self.drag_y_root_start = event.y_root
        self.is_real_drag = False
        return "break"
        
    def do_drag(self, event):
        """拖动中：视觉跟随 + 实时移动占位符"""
        if not self.drag_obj: return "break"
        
        if not self.is_real_drag and abs(event.y_root - self.drag_y_root_start) > 5:
            self.is_real_drag = True
            # 变淡显示，增强拖拽感
            self.drag_obj.config(bg=self.themes[self.current_theme.get()]["active"])
            # 展示占位符
            self.placeholder.pack(fill="x", padx=5, pady=2, before=self.drag_obj)
        
        if self.is_real_drag:
            # 视觉跟随
            new_y = event.y_root - self.cmd_container.winfo_rooty() - self.drag_y_origin
            self.drag_obj.place(x=0, y=new_y, relwidth=1)
            self.drag_obj.lift() 
            
            # 逻辑交换
            target_y = event.y_root - self.cmd_container.winfo_rooty()
            children = [c for c in self.cmd_container.winfo_children() if c != self.drag_obj and c != self.placeholder]
            
            new_idx = 0
            for i, child in enumerate(children):
                cy, ch = child.winfo_y(), child.winfo_height()
                if target_y > cy + ch/2:
                    new_idx = i + 1
            
            if hasattr(self, 'current_p_idx') and self.current_p_idx == new_idx:
                pass 
            else:
                self.current_p_idx = new_idx
                self.placeholder.pack_forget()
                if new_idx < len(children):
                    self.placeholder.pack(fill="x", padx=5, pady=2, before=children[new_idx])
                else:
                    self.placeholder.pack(fill="x", padx=5, pady=2)
                    
        return "break"

    def stop_drag(self, event):
        """松开鼠标：根据占位符最终位置更新数据并重绘"""
        if not self.drag_obj: return "break"
        
        if not self.is_real_drag:
            self.send_to_target(self.drag_text)
        else:
            children = [c for c in self.cmd_container.winfo_children() if c != self.drag_obj]
            final_idx = children.index(self.placeholder)
            item = self.commands.pop(self.drag_start_idx)
            self.commands.insert(final_idx, item)
            self.save_config()
            
        if hasattr(self, 'current_p_idx'): del self.current_p_idx
        self.drag_obj.place_forget()
        self.drag_obj = None
        self.refresh_cmd_list()
        return "break"

    # --- 窗口交互（移动/缩放）实现方法 ---
    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.win_w, self.win_h = self.root.winfo_width(), self.root.winfo_height()
        if event.x > self.win_w - self.EDGE_SIZE and event.y > self.win_h - self.EDGE_SIZE: self.mode = "resize_both"
        elif event.x > self.win_w - self.EDGE_SIZE: self.mode = "resize_w"
        elif event.y > self.win_h - self.EDGE_SIZE: self.mode = "resize_h"
        else: self.mode = "move"

    def on_motion(self, event):
        MIN_WIDTH = 180  # 最小宽度限制
        MIN_HEIGHT = 150  # 最小高度限制
        if self.mode == "move":
            self.root.geometry(f"+{self.root.winfo_x() + event.x - self.start_x}+{self.root.winfo_y() + event.y - self.start_y}")
        elif self.mode == "resize_w": 
            self.root.geometry(f"{max(MIN_WIDTH, event.x)}x{self.win_h}")
            self.root.update_idletasks()
        elif self.mode == "resize_h": 
            self.root.geometry(f"{self.win_w}x{max(MIN_HEIGHT, event.y)}")
            self.root.update_idletasks()
        elif self.mode == "resize_both": 
            self.root.geometry(f"{max(MIN_WIDTH, event.x)}x{max(MIN_HEIGHT, event.y)}")
            self.root.update_idletasks()
        self.save_config()

    def update_cursor(self, event):
        x, y = event.x, event.y
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if x > w - self.EDGE_SIZE and y > h - self.EDGE_SIZE: self.root.config(cursor="size_nw_se")
        elif x > w - self.EDGE_SIZE: self.root.config(cursor="size_we")
        elif y > h - self.EDGE_SIZE: self.root.config(cursor="size_ns")
        else: self.root.config(cursor="arrow")

    # --- 自动化工作流逻辑 ---
    def send_to_target(self, text):
        """在新线程中启动自动化任务，避免界面卡死"""
        threading.Thread(target=self._automation_task, args=(text,), daemon=True).start()

    def enable_cmd_shortcuts(self):
        """自动开启 Windows 控制台的 Ctrl+V 和右键粘贴支持"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Console", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "FilterOnPaste", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "InterceptCopyPaste", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
        except: pass
    def _automation_task(self, prompt):
        """核心自动化流程：寻找窗口 -> 激活 -> 模拟输入"""
        # 1. 立即记录原始鼠标位置（在任何窗口激活操作之前）
        old_pos = pyautogui.position()
        
        ide = self.current_ide.get()
        ai = self.current_ai.get()
        config = self.target_settings[ide][ai]
        
        # 安全检查：未校准则禁止点击图标模式
        if ide != "Native CLI" and config.get("offset_x", 0) == 0 and config.get("offset_y", 0) == 0:
            messagebox.showwarning("需要校准", f"当前目标 [{ide} -> {ai}] 尚未校准，请先点击底部的🎯按钮。")
            return

        try:
            all_wins = Desktop(backend="uia").windows()
            terminal_wins = []
            target_regex = config["win_title"]
            for win in all_wins:
                try:
                    title, cls = win.window_text(), win.element_info.class_name
                    if re.search(target_regex, title, re.I) or cls == "ConsoleWindowClass":
                        # 仅排除明确最小化的窗口
                        if not win.get_show_state() == 2:
                            terminal_wins.append(win)
                except: continue
            
            # --- 核心修复：如果 UIA 匹配不到，启用 win32gui 暴力扫描 ---
            if not terminal_wins and win32gui:
                print(f"UIA 扫描未果，正在启动 win32 暴力扫描模式... Regex: {target_regex}")
                def enum_callback(hwnd, results):
                    if win32gui.IsWindowVisible(hwnd):
                        t = win32gui.GetWindowText(hwnd)
                        c = win32gui.GetClassName(hwnd)
                        if t and (re.search(target_regex, t, re.I) or c == "ConsoleWindowClass"):
                            results.append((hwnd, t))
                
                win32_results = []
                win32gui.EnumWindows(enum_callback, win32_results)
                
                if win32_results:
                    from pywinauto import Application
                    for hwnd, t in win32_results:
                        print(f"win32 模式找到匹配: {t} (HWND: {hwnd})")
                        # 将 win32 句柄包装成 pywinauto 窗口对象
                        app_win32 = Application(backend="win32").connect(handle=hwnd)
                        terminal_wins.append(app_win32.window(handle=hwnd))
            
            if not terminal_wins: 
                print(f"!!! 最终仍未能匹配到任何目标窗口。")
                return
            
            target_win = terminal_wins[0]
            try:
                # 尝试多种激活方式
                if hasattr(target_win, 'set_focus'):
                    target_win.set_focus()
                elif win32gui:
                    hwnd = target_win.wrapper_object().handle
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.1)
            except Exception as e:
                print(f"激活窗口失败: {e}")
                return

            if ide == "Native CLI":
                self.enable_cmd_shortcuts()
                pyperclip.copy(prompt)
                time.sleep(0.05)
                rect = target_win.rectangle()
                pyautogui.moveTo((rect.left + rect.right)//2, (rect.top + rect.bottom)//2)
                time.sleep(0.05); pyautogui.rightClick()
                if self.auto_send.get(): pyautogui.press('enter')
                pyautogui.moveTo(old_pos)
            else:
                try:
                    # 检查锚点图片文件是否存在（处理首次使用或文件丢失）
                    if not os.path.exists(config["image"]):
                        if messagebox.askyesno("QuickBar", self.t("calibration_tip")):
                            self.root.after(100, self.start_calibration)
                        return

                    loc = pyautogui.locateOnScreen(config["image"], confidence=0.7)
                    if loc:
                        pyautogui.click(loc.left + loc.width/2 + config.get("offset_x", 0), 
                                        loc.top + loc.height/2 + config["offset_y"])
                        time.sleep(0.05)
                        # 增加清空逻辑的容错
                        pyautogui.hotkey('ctrl', 'a')
                        time.sleep(0.05)
                        pyautogui.press('backspace') 
                        pyperclip.copy(prompt)
                        time.sleep(0.05)
                        pyautogui.hotkey('ctrl', 'v') 
                        if self.auto_send.get(): 
                            time.sleep(0.05)
                            pyautogui.press('enter')
                        
                        # 完成后返回原始位置
                        pyautogui.moveTo(old_pos)
                    else:
                        print(f"未能在此窗口找到锚点图像: {config['image']}")
                except Exception as e:
                    import traceback
                    print(f"识别或模拟点击失败详细日志:\n{traceback.format_exc()}")
                    if "Failed to read" in str(e):
                        messagebox.showerror("图片加载失败", f"校准图片文件损坏或无法读取：\n{config['image']}\n建议重新点击校准按钮。")
        except Exception as e: 
            print(f"自动化核心流程异常: {e}")

    # --- 辅助弹窗方法 ---
    def add_command_dialog(self):
        d = EditDialog(self, "新增指令", "", "", self.themes[self.current_theme.get()])
        if d.result: 
            self.commands.append({"name": d.result[0], "text": d.result[1]})
            self.save_config(); self.setup_ui()

    def edit_command_dialog(self, cmd):
        d = EditDialog(self, "编辑指令", cmd['name'], cmd['text'], self.themes[self.current_theme.get()])
        if d.result: 
            cmd['name'], cmd['text'] = d.result
            self.save_config(); self.setup_ui()

    def show_context_menu(self, event, cmd, idx):
        """显示右键上下文菜单"""
        colors = self.themes[self.current_theme.get()]
        menu = tk.Menu(self.root, tearoff=0, bg=colors["header"], fg=colors["text"],
                       activebackground=colors["active"], activeforeground="white",
                       font=("Microsoft YaHei", 9))
        menu.add_command(label="编辑", command=lambda: self.edit_command_dialog(cmd))
        menu.add_command(label="删除", command=lambda: self.delete_command(idx))
        menu.tk_popup(event.x_root, event.y_root)

    def delete_command(self, idx):
        """删除指定索引的指令"""
        cmd = self.commands[idx]
        colors = self.themes[self.current_theme.get()]
        
        # 创建自定义确认对话框，显示在主窗口附近
        dialog = tk.Toplevel(self.root)
        dialog.title("确认删除")
        dialog.geometry(f"250x120+{self.root.winfo_x()+20}+{self.root.winfo_y()+50}")
        dialog.configure(bg=colors["bg"])
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        dialog.grab_set()
        
        tk.Label(dialog, text=f"是否删除指令 '{cmd['name']}'?", 
                bg=colors["bg"], fg=colors["text"], 
                font=("Microsoft YaHei", 9), wraplength=220).pack(pady=20)
        
        btn_frame = tk.Frame(dialog, bg=colors["bg"])
        btn_frame.pack(pady=10)
        
        def on_yes():
            self.commands.pop(idx)
            self.save_config()
            dialog.destroy()
            self.setup_ui()
        
        tk.Button(btn_frame, text="是", bg=colors["active"], fg="white", 
                 relief="flat", width=8, command=on_yes).pack(side="left", padx=10)
        tk.Button(btn_frame, text="否", bg=colors["btn"], fg=colors["text"], 
                 relief="flat", width=8, command=dialog.destroy).pack(side="left", padx=10)



    def start_calibration(self):
        """启动两阶段校准：截图特征图 -> 点击目标位置"""
        ide, ai = self.current_ide.get(), self.current_ai.get()
        config = self.target_settings[ide][ai]
        scr = ScreenshotDialog(self.root, config["image"], f"校准 - 步骤 1: 请框选特征锚点")
        if scr.success:
            loc = LocationDialog(self.root, config["image"], f"校准 - 步骤 2: 请点击目标输入框中心")
            if loc.success:
                ax, ay = loc.anchor_pos
                cx, cy = loc.click_pos
                config["offset_x"], config["offset_y"] = cx - ax, cy - ay
                with open(TARGET_CONFIG_FILE, "w", encoding="utf-8") as f: 
                    json.dump(self.target_settings, f, indent=4)
                messagebox.showinfo("成功", "校准数据已保存")
                self.save_config()
                self.setup_ui()

    def auto_adjust_height(self):
        """根据当前 UI 元素内容自动计算并调整窗口高度"""
        self.root.update_idletasks()
        
        # 计算所有顶级 pack 出来的组件所需的高度
        total_h = 0
        for child in self.root.winfo_children():
            # 排除 place 布局的拖拽对象
            if child.winfo_manager() == 'pack':
                total_h += child.winfo_reqheight()
        
        # 获取当前窗口的 X 坐标和宽度
        curr_geom = self.root.geometry().split('+')
        w_str = curr_geom[0].split('x')[0]
        curr_x = curr_geom[1]
        curr_y = curr_geom[2]
        
        # 加上足够的安全余量（底部工具栏 + 边距）
        new_h = total_h + 20
        
        # 限制高度：不宜过小也不宜超过屏幕
        screen_h = self.root.winfo_screenheight()
        final_h = min(max(new_h, 150), screen_h - 100)
        
        self.root.geometry(f"{w_str}x{final_h}+{curr_x}+{curr_y}")
        self.save_config()

class EditDialog(tk.Toplevel):
    """自适应主题的指令编辑弹窗"""
    def __init__(self, app, title, name, text, colors):
        super().__init__(app.root)
        self.title(title); self.result = None
        self.geometry(f"300x260+{app.root.winfo_x()+20}+{app.root.winfo_y()+100}")
        self.attributes("-topmost", True); self.resizable(False, False)
        self.configure(bg=colors["bg"])
        
        tk.Label(self, text="按钮名称:", bg=colors["bg"], fg=colors["subtext"]).pack(padx=10, anchor="w", pady=(10,0))
        self.ne = tk.Entry(self, bg=colors["btn"], fg=colors["text"], insertbackground=colors["text"], relief="flat")
        self.ne.insert(0, name); self.ne.pack(padx=10, pady=5, fill="x")
        
        tk.Label(self, text="指令内容:", bg=colors["bg"], fg=colors["subtext"]).pack(padx=10, anchor="w")
        self.ta = tk.Text(self, bg=colors["btn"], fg=colors["text"], insertbackground=colors["text"], relief="flat", height=6)
        self.ta.insert("1.0", text); self.ta.pack(padx=10, pady=5, fill="x")
        
        bf = tk.Frame(self, bg=colors["bg"]); bf.pack(pady=10)
        tk.Button(bf, text="确定", width=10, bg=colors["active"], fg="white", relief="flat", 
                  command=self.on_save).pack(side="left", padx=5)
        tk.Button(bf, text="取消", width=10, bg=colors["btn"], fg=colors["subtext"], relief="flat", 
                  command=self.destroy).pack(side="left", padx=5)
        self.grab_set(); self.wait_window()

    def on_save(self):
        n, t = self.ne.get().strip(), self.ta.get("1.0", "end-1c").strip()
        if not t: return # 指令内容不能为空
        
        # 如果按钮名称没有填写，则默认采用指令内容的前 10 个字符
        if not n:
            n = (t[:10] + "..") if len(t) > 10 else t
            
        self.result = (n, t)
        self.destroy()

class ScreenshotDialog:
    def __init__(self, parent, filename, prompt):
        self.filename, self.success = filename, False
        self.root = tk.Toplevel(parent)
        self.root.attributes("-fullscreen", True, "-alpha", 0.2, "-topmost", True)
        self.canvas = tk.Canvas(self.root, cursor="arrow", bg="grey"); self.canvas.pack(fill="both", expand=True)
        self.zoom_size, self.zoom_scale = 180, 4
        self.z_win = tk.Toplevel(self.root); self.z_win.overrideredirect(True); self.z_win.attributes("-topmost", True)
        self.z_can = tk.Canvas(self.z_win, width=self.zoom_size, height=self.zoom_size, highlightthickness=2, highlightbackground="yellow")
        self.z_can.pack()
        # 添加背景文字阴影使提示更清晰
        self.canvas.create_text(self.root.winfo_screenwidth()/2 + 2, 52, text=prompt, fill="black", font=("Microsoft YaHei", 20, "bold"))
        self.canvas.create_text(self.root.winfo_screenwidth()/2, 50, text=prompt, fill="#00FF00", font=("Microsoft YaHei", 20, "bold"))
        
        self.canvas.create_text(self.root.winfo_screenwidth()/2 + 1, 86, text="(按 ESC 键取消校准)", fill="black", font=("Microsoft YaHei", 10, "bold"))
        self.canvas.create_text(self.root.winfo_screenwidth()/2, 85, text="(按 ESC 键取消校准)", fill="white", font=("Microsoft YaHei", 10, "bold"))
        self.start_x = self.start_y = self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", lambda e: self.update_zoom(e.x_root, e.y_root))
        # 修复：拖拽时也要同步更新放大镜
        self.canvas.bind("<B1-Motion>", lambda e: [self.on_drag(e), self.update_zoom(e.x_root, e.y_root)], add="+")
        self.root.bind("<Escape>", lambda e: self.root.destroy()) # 支持 ESC 退出
        parent.wait_window(self.root)

    def update_zoom(self, x, y):
        r = self.zoom_size // (2 * self.zoom_scale)
        shot = ImageGrab.grab(bbox=(x-r, y-r, x+r, y+r)).resize((self.zoom_size, self.zoom_size), Image.NEAREST)
        self.z_img = ImageTk.PhotoImage(shot)
        self.z_can.delete("all"); self.z_can.create_image(0, 0, anchor="nw", image=self.z_img)
        m = self.zoom_size // 2
        self.z_can.create_line(m,0,m,m-5,fill="red"); self.z_can.create_line(m,m+5,m,self.zoom_size,fill="red")
        self.z_can.create_line(0,m,m-5,m,fill="red"); self.z_can.create_line(m+5,m,self.zoom_size,m,fill="red")
        self.z_can.create_oval(m-5,m-5,m+5,m+5,outline="yellow",width=2)
        zx, zy = (x+60 if x+240<self.root.winfo_screenwidth() else x-240), (y+60 if y+240<self.root.winfo_screenheight() else y-240)
        self.z_win.geometry(f"+{int(zx)}+{int(zy)}")

    def on_press(self, e): self.start_x, self.start_y = e.x, e.y; self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y, outline='red', width=2)
    def on_drag(self, e): self.canvas.coords(self.rect, self.start_x, self.start_y, e.x, e.y)
    def on_release(self, e):
        x1, y1, x2, y2 = min(self.start_x, e.x), min(self.start_y, e.y), max(self.start_x, e.x), max(self.start_y, e.y)
        if x2-x1 > 5: ImageGrab.grab(bbox=(x1, y1, x2, y2)).save(self.filename); self.success = True; self.z_win.destroy(); self.root.destroy()

class LocationDialog:
    def __init__(self, parent, image_path, prompt):
        self.success, self.image_path = False, image_path
        self.root = tk.Toplevel(parent); self.root.attributes("-fullscreen", True, "-alpha", 0.2, "-topmost", True)
        self.canvas = tk.Canvas(self.root, cursor="arrow", bg="grey"); self.canvas.pack(fill="both", expand=True)
        self.zoom_size, self.zoom_scale = 180, 4
        self.z_win = tk.Toplevel(self.root); self.z_win.overrideredirect(True); self.z_win.attributes("-topmost", True)
        self.z_can = tk.Canvas(self.z_win, width=self.zoom_size, height=self.zoom_size, highlightthickness=2, highlightbackground="yellow")
        self.z_can.pack()
        # 添加背景文字阴影使提示更清晰
        self.canvas.create_text(self.root.winfo_screenwidth()/2 + 2, 52, text=prompt, fill="black", font=("Microsoft YaHei", 20, "bold"))
        self.canvas.create_text(self.root.winfo_screenwidth()/2, 50, text=prompt, fill="#00FFFF", font=("Microsoft YaHei", 20, "bold"))
        
        self.canvas.create_text(self.root.winfo_screenwidth()/2 + 1, 86, text="(按 ESC 键取消校准)", fill="black", font=("Microsoft YaHei", 10, "bold"))
        self.canvas.create_text(self.root.winfo_screenwidth()/2, 85, text="(按 ESC 键取消校准)", fill="white", font=("Microsoft YaHei", 10, "bold"))
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", lambda e: self.update_zoom(e.x_root, e.y_root))
        self.canvas.bind("<B1-Motion>", lambda e: self.update_zoom(e.x_root, e.y_root))
        self.root.bind("<Escape>", lambda e: self.root.destroy()) # 支持 ESC 退出
        parent.wait_window(self.root)

    def update_zoom(self, x, y):
        r = self.zoom_size // (2 * self.zoom_scale)
        shot = ImageGrab.grab(bbox=(x-r, y-r, x+r, y+r)).resize((self.zoom_size, self.zoom_size), Image.NEAREST)
        self.z_img = ImageTk.PhotoImage(shot)
        self.z_can.delete("all"); self.z_can.create_image(0, 0, anchor="nw", image=self.z_img)
        m = self.zoom_size // 2
        self.z_can.create_line(m,0,m,m-5,fill="red"); self.z_can.create_line(m,m+5,m,self.zoom_size,fill="red")
        self.z_can.create_line(0,m,m-5,m,fill="red"); self.z_can.create_line(m+5,m,self.zoom_size,m,fill="red")
        self.z_can.create_oval(m-5,m-5,m+5,m+5,outline="yellow",width=2)
        zx, zy = (x+60 if x+240<self.root.winfo_screenwidth() else x-240), (y+60 if y+240<self.root.winfo_screenheight() else y-240)
        self.z_win.geometry(f"+{int(zx)}+{int(zy)}")

    def on_click(self, e):
        self.click_pos = (e.x, e.y); self.root.withdraw(); self.z_win.withdraw(); self.root.update(); time.sleep(0.2)
        try:
            loc = pyautogui.locateOnScreen(self.image_path, confidence=0.7)
            if loc: self.anchor_pos = (loc.left+loc.width/2, loc.top+loc.height/2); self.success = True
            else: messagebox.showerror("错误", "无法定位特征图")
        except Exception as ex: messagebox.showerror("错误", str(ex))
        self.z_win.destroy(); self.root.destroy()

if __name__ == "__main__":
    # 单实例检测：尝试绑定一个不常用的端口
    try:
        # 我们需要保持这个 socket 对象的引用，直到程序退出
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 12456))
    except socket.error:
        # 端口已被占用，说明已有实例运行
        messagebox.showwarning("QuickBar", "程序已经在运行中！")
        sys.exit(0)

    root = tk.Tk()
    QuickBarApp(root)
    root.mainloop()
