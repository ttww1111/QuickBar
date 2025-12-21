import os
import subprocess
import shutil

def build():
    # 1. 确保环境
    print("正在安装打包依赖...")
    subprocess.run(["pip", "install", "pyinstaller"], check=True)

    # 2. 清理旧的构建文件夹
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
    
    # 3. 执行 PyInstaller
    # --onefile (-F): 打包成单一可执行文件
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=QuickBar",
        "--icon=vscode_icon.png",
        "--add-data=assets;assets",
        # 注意：config 和 target_settings 不打包进 exe，因为需要用户修改和保存
        "QuickBar.py"
    ]
    
    print(f"正在执行打包命令: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    print("\n" + "="*30)
    print("打包完成！可执行文件位于: dist/QuickBar/QuickBar.exe")
    print("请注意：分发时需要带上整个 dist/QuickBar 文件夹内容。")
    print("="*30)

if __name__ == "__main__":
    build()
