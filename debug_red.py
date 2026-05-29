"""诊断工具：分析聊天列表截图中所有偏红色像素，找到未读标记的真实颜色。"""
import os
from pathlib import Path
from collections import Counter, defaultdict
from PIL import Image
import yaml

debug_dir = Path(__file__).parent / "debug"
img_path = debug_dir / "chat_list.png"

if not img_path.exists():
    print("请先运行 main.py 生成 debug/chat_list.png")
    exit(1)

img = Image.open(img_path)
w, h = img.size
print(f"图片尺寸: {w}x{h}")

# 收集所有偏红像素（非常宽松的阈值）
reddish = []
for y in range(h):
    for x in range(w):
        try:
            r, g, b = img.getpixel((x, y))[:3]
            # 宽松条件：红色通道明显高于蓝色通道
            if r > 100 and r > g and r > b and (r - b) > 30:
                reddish.append((x, y, r, g, b))
        except:
            continue

print(f"偏红像素总数: {len(reddish)}")

if not reddish:
    print("\n没找到任何偏红像素！尝试更宽松的条件...")
    for y in range(h):
        for x in range(w):
            try:
                r, g, b = img.getpixel((x, y))[:3]
                if r > 80 and r >= g and r >= b:
                    reddish.append((x, y, r, g, b))
            except:
                continue
    print(f"极宽松条件偏红像素: {len(reddish)}")

if reddish:
    # 统计最常见的 RGB 值
    rgb_counter = Counter((r, g, b) for _, _, r, g, b in reddish)
    print("\n最常见的偏红 RGB 值 (Top 20):")
    for (r, g, b), count in rgb_counter.most_common(20):
        print(f"  RGB({r}, {g}, {b}) x{count}")

    # 按 y 坐标聚类
    y_clusters = defaultdict(list)
    for x, y, r, g, b in reddish:
        y_clusters[y].append((x, r, g, b))

    # 找出像素集中的行
    print("\n偏红像素集中的行 (>=3 pixels):")
    for y in sorted(y_clusters):
        count = len(y_clusters[y])
        if count >= 3:
            row_pixels = y_clusters[y]
            avg_r = sum(p[1] for p in row_pixels) / len(row_pixels)
            xs = [p[0] for p in row_pixels]
            print(f"  y={y}: {count} pixels, avg R={avg_r:.0f}, x_range=[{min(xs)}-{max(xs)}]")

    # 找到连续的红像素区域
    y_sorted = sorted(set(y for _, y, _, _, _ in reddish if len(y_clusters.get(y, [])) >= 2))
    if y_sorted:
        clusters = []
        start = y_sorted[0]
        prev = y_sorted[0]
        for y in y_sorted[1:]:
            if y - prev > 5:
                clusters.append((start, prev))
                start = y
            prev = y
        clusters.append((start, prev))

        config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        item_height = config.get("wechat", {}).get("layout", {}).get("chat_item_height", 94)

        print("\n红色区域聚类 (含 x 范围):")
        for y_start, y_end in clusters:
            idx = (y_start + y_end) // 2 // item_height
            # 取该区域所有像素的 x 范围
            cluster_pixels = [(x, r, g, b) for x, y, r, g, b in reddish if y_start <= y <= y_end]
            if cluster_pixels:
                xs = [p[0] for p in cluster_pixels]
                avg_rgb = tuple(sum(p[i+1] for p in cluster_pixels) // len(cluster_pixels) for i in range(3))
                cluster_w = max(xs) - min(xs)
                cluster_h = y_end - y_start
                size = len(cluster_pixels)
                print(f"  y={y_start}-{y_end}, idx={idx}, RGB={avg_rgb}, "
                      f"x=[{min(xs)}-{max(xs)}] w={cluster_w}, h={cluster_h}, px={size}")

        # 重点：找出小面积高饱和度红色区域（最可能是未读标记）
        print("\n疑似未读标记（小面积 + 高红饱和度）:")
        for y_start, y_end in clusters:
            cluster_pixels = [(x, r, g, b) for x, y, r, g, b in reddish if y_start <= y <= y_end]
            if not cluster_pixels:
                continue
            xs = [p[0] for p in cluster_pixels]
            cluster_w = max(xs) - min(xs)
            cluster_h = y_end - y_start
            size = len(cluster_pixels)
            avg_r = sum(p[1] for p in cluster_pixels) / len(cluster_pixels)
            avg_g = sum(p[2] for p in cluster_pixels) / len(cluster_pixels)
            avg_b = sum(p[3] for p in cluster_pixels) / len(cluster_pixels)
            # 小面积 + 高红饱和度 = 可能是未读标记
            if 10 < size < 800 and avg_r > 180 and avg_g < 100 and avg_b < 100:
                mid_y = (y_start + y_end) // 2
                idx = mid_y // item_height
                print(f"  y={y_start}-{y_end} (idx={idx}): RGB=({avg_r:.0f},{avg_g:.0f},{avg_b:.0f}), "
                      f"x=[{min(xs)}-{max(xs)}] w={cluster_w} h={cluster_h}, size={size}px")
else:
    print("\n完全没找到偏红像素，未读标记可能不是红色的。")
    print("请检查 debug/chat_list.png 中未读标记的实际颜色和位置。")
