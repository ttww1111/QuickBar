# QuickBar 🚀

QuickBar 是一款专为开发者设计的**极简、高效**的提示词（Prompt）管理与自动化输入工具。它可以帮助你一键将常用的指令、代码片段或提示词发送到目标 IDE（如 VS Code）中的 AI 助手窗口或原生终端中。

![QuickBar 主界面](assets/quickbar_icon.png)

## ✨ 核心特性

-   **🎯 跨工具支持**：预设支持 VS Code (Claude/Codex), Google Antigravity, 以及原生终端 (PowerShell/CMD)。
-   **⚡ 一键自动化**：通过图像识别（锚点匹配）技术，自动激活目标窗口、寻找输入框、粘贴并发送内容。
-   **🎨 现代美学设计**：
    -   无边框科技感界面，支持 **深色/浅色** 主题一键切换。
    -   支持透明度调节与**窗口置顶**。
    -   按钮列表圆角设计，支持**拖拽排序**。
-   **🔧 智能自动化流程**：
    -   **两阶段校准**：简单的截图 + 点击即可适配任何分辨率下的 AI 输入框。
    -   **自动发送**：内容填入后可选是否自动按下回车。
    -   **焦点还原**：操作完成后自动将鼠标移回原位，不打断思路。
-   **📦 零配置上手**：
    -   单文件绿色运行（基于 Python + Tkinter）。
    -   支持开机自启、最小化到托盘、配置导入导出。
-   **🌐 多语言支持**：内置中文、英文、日文界面支持。

## 🚀 快速开始

### 1. 安装环境
确保已安装 Python，并安装以下依赖：
```bash
pip install pyautogui pyperclip pillow pywinauto pystray pywin32
```

### 2. 运行程序
直接运行源代码：
```bash
python QuickBar.py
```

### 3. 配置与使用
1.  **选择目标**：在顶部图标区域选择你正在使用的 IDE（如 VS Code）和对应的 AI 助手（如 Claude）。
2.  **首次校准**：点击底部的 🎯 按钮。
    -   **步骤 1**：框选输入框周围的一个特征点（如输入框图标）。
    -   **步骤 2**：在弹出的全屏截图中点击输入框的中心位置。
3.  **发送内容**：点击列表中的指令按钮，QuickBar 会自动完成窗口切换和输入。

## 🛠️ 技术实现

-   **GUI 框架**：Tkinter（经过深度定制，实现现代无边框 UI）。
-   **自动化控制**：PyAutoGUI (鼠标键盘模拟) + pywinauto (窗口定位与激活)。
-   **图像处理**：Pillow (截图、图片旋转、主题适配)。
-   **持久化**：JSON 文件存储指令和窗口校准数据。

## 📂 项目结构

```text
QuickBar/
├── QuickBar.py           # 主程序代码
├── config.json           # 存储自定义指令和应用状态
├── target_settings.json  # 存储不同 IDE 的校准偏移数据
├── assets/               # 资源文件夹
│   ├── anchors/          # 存储用户生成的校准锚点图
│   └── *.png             # UI 图标资源
└── tools/                # 辅助开发工具
```

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request 来改进 QuickBar！

-   **GitHub**: [QuickBar Repo](https://github.com/user/quickbar)
-   **License**: MIT

---
*保持专注，让 Prompt 随手即得。*
