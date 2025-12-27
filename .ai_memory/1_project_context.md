# 项目核心知识库

## 项目目标
QuickBar 是一个桌面快捷指令工具，旨在通过 GUI 界面快速向目标 IDE（VS Code, Antigravity）或终端发送预设指令。

## 核心共识
1. **自动化方案**：使用 `pywinauto` 和 `win32gui` 进行窗口匹配，`pyautogui` 模拟点击和输入。
2. **讯飞语音集成**：采用严格还原 `Agile-Win-Hotkey-for-iFlyVoice` 的逻辑。
   - 类名过滤：`ahk_class BaseGui`
   - 进程名过滤：`ahk_exe iFlyVoice.exe`
   - 触发坐标：`(119, 59)`
   - 激活策略：`SWP_NOACTIVATE` + `HWND_TOPMOST` 物理脉冲，不夺取当前窗口焦点。
3. **UI 刷新架构**：
   - 采用“原地局部刷新”替代“全量重建”，通过 `config` 修改组件属性消除闪烁。
   - 仅在 IDE 模式切换涉及结构突变（如 Native CLI 显隐）时触发容器级重建。
4. **视觉对齐规范**：
   - 不同字体基线对齐必须使用非对称 `pady` 补丁。
   - 默认补丁偏好：文字下沉（基线补偿），图标上移。
5. **部署策略**：
   - `assets/anchors` 目录及其内容应外置于 EXE 运行目录，以保证校准数据的持久化与可读性。
6. **Win+H 拦截与重映射**：
   - 使用 `SetWindowsHookExW` 挂载全局键盘钩子压制系统原生 UI。
   - **重映射逻辑**：当检测到 `Win+Alt+H` 时，通过物理释放 Alt 键并注入 H 脉冲，模拟纯净的 `Win+H` 以唤起系统原生听写。
