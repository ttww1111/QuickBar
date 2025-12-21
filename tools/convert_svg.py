import cairosvg
import os

# SVG 到 PNG 的映射
conversions = {
    'Vscode.svg': 'vscode_icon.png',
    'Antigravity.svg': 'antigravity_icon.png',
    'Claude.svg': 'claude_icon.png',
    'Codex.svg': 'codex_icon.png'
}

for svg_file, png_file in conversions.items():
    if os.path.exists(svg_file):
        try:
            # 转换为 256x256 的 PNG（高清源文件，程序运行时会缩放）
            cairosvg.svg2png(url=svg_file, write_to=png_file, output_width=256, output_height=256)
            print(f"✓ 已转换: {svg_file} -> {png_file}")
        except Exception as e:
            print(f"✗ 转换失败 {svg_file}: {e}")
    else:
        print(f"✗ 文件不存在: {svg_file}")

print("\n转换完成！")
