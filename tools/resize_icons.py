from PIL import Image
import os

def resize_icons():
    # 定义需要处理的图标及其目标路径（如果是同一文件则覆盖）
    icons = {
        "Codex.png": 32,
        "Claude.png": 32,
        "Vscode.png": 32,
        "Antigravity.png": 32
    }
    
    for filename, size in icons.items():
        if os.path.exists(filename):
            try:
                with Image.open(filename) as img:
                    # 使用 Image.LANCZOS 进行高质量缩放
                    # 调整为统一的正方形尺寸 32x32 (适合 UI 显示且保持清晰)
                    img_resized = img.resize((size, size), Image.LANCZOS)
                    img_resized.save(filename)
                    print(f"Successfully resized {filename} to {size}x{size}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")
        else:
            print(f"File {filename} not found.")

if __name__ == "__main__":
    resize_icons()
