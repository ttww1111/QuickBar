from PIL import Image
import os

files = ['vscode_icon.png', 'antigravity_icon.png', 'terminal_icon.png']

for f in files:
    if os.path.exists(f):
        img = Image.open(f)
        print(f"{f}: 尺寸={img.size}, 模式={img.mode}")
        
        # 检查实际内容边界（非透明区域）
        if img.mode == 'RGBA':
            bbox = img.getbbox()
            if bbox:
                print(f"  实际内容区域: {bbox}, 内容尺寸: {bbox[2]-bbox[0]}x{bbox[3]-bbox[1]}")
            else:
                print(f"  图片完全透明或无内容")
    else:
        print(f"{f}: 文件不存在")
