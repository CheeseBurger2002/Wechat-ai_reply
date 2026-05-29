"""微信控制器 — 基于截图 + OCR + 坐标点击的纯模拟操作。"""
import os
os.environ.setdefault('FLAGS_use_mkldnn', '0')

import time
import re
import random
import ctypes
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import numpy as np
import uiautomation as auto
import pyautogui
from PIL import Image

logger = logging.getLogger("wx_reply")

# 安全设置：防止鼠标飞出屏幕
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.02


@dataclass
class WeChatLayout:
    """微信窗口布局坐标（均为窗口内相对坐标）。"""
    # 聊天列表区域
    chat_list_left: int = 0
    chat_list_top: int = 30
    chat_list_width: int = 250
    chat_list_bottom: int = 0  # 0 = 窗口高度

    # 每个聊天项的高度
    chat_item_height: int = 68

    # 消息区域
    msg_area_left: int = 260
    msg_area_top: int = 45
    msg_area_right: int = 0   # 0 = 窗口宽度
    msg_area_bottom: int = 165  # 距离窗口底部的偏移

    # 输入框
    input_left: int = 270
    input_top_offset: int = 130  # 距离窗口底部的偏移
    input_width: int = 0         # 0 = 窗口宽度 - input_left - 20
    input_height: int = 30


class WeChatController:
    """通过截图 + OCR + 鼠标键盘模拟操作 PC 微信。"""

    WINDOW_NAME = "微信"
    WINDOW_CLASS = "Qt51514QWindowIcon"

    def __init__(self, layout: WeChatLayout | None = None):
        self.layout = layout or WeChatLayout()
        self._window_rect: Optional[auto.Rect] = None

    # ─── 窗口管理 ─────────────────────────────────

    def find_window(self) -> bool:
        wechat = auto.WindowControl(Name=self.WINDOW_NAME,
                                     ClassName=self.WINDOW_CLASS)
        if not wechat.Exists(maxSearchSeconds=3):
            wechat = auto.WindowControl(ClassName=self.WINDOW_CLASS)
            if not wechat.Exists(maxSearchSeconds=3):
                logger.error("WeChat window not found")
                return False

        self._window_rect = wechat.BoundingRectangle
        logger.info(f"WeChat window: {self._rect_info()}")
        return True

    def ensure_window(self, foreground: bool = False) -> bool:
        if self._window_rect is None:
            if not self.find_window():
                return False

        wechat = auto.WindowControl(Name=self.WINDOW_NAME,
                                     ClassName=self.WINDOW_CLASS)
        if not wechat.Exists():
            return self.find_window()

        self._window_rect = wechat.BoundingRectangle

        if foreground:
            self._force_foreground(wechat)
        else:
            wechat.SetFocus()
        return True

    def _force_foreground(self, wechat) -> None:
        """强制将微信窗口拉到前台（解决长时间延迟后被其他窗口遮挡的问题）。"""
        user32 = ctypes.windll.user32
        try:
            hwnd = wechat.NativeWindowHandle
            if hwnd == 0:
                hwnd = user32.FindWindowW("Qt51514QWindowIcon", "微信")
            if hwnd == 0:
                logger.warning("Cannot find WeChat HWND for foreground")
                wechat.SetFocus()
                return

            # 已经在前台就不需要操作
            if user32.GetForegroundWindow() == hwnd:
                return

            # 如果最小化了，先还原窗口
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                time.sleep(0.05)

            # Alt 键技巧：先模拟 Alt 按下，让本进程获得前台权限，
            # 然后调用 SetForegroundWindow，再释放 Alt
            user32.keybd_event(0x12, 0, 0, 0)   # Alt down
            result = user32.SetForegroundWindow(hwnd)
            user32.keybd_event(0x12, 0, 2, 0)   # Alt up
            if result == 0:
                logger.warning("SetForegroundWindow failed")
            else:
                logger.debug("WeChat window forced to foreground")
        except Exception as e:
            logger.debug(f"Force foreground failed: {e}, using SetFocus")
            wechat.SetFocus()

    def _rect_info(self) -> str:
        r = self._window_rect
        return f"({r.left}, {r.top}) {r.width()}x{r.height()}"

    # ─── 坐标转换 ─────────────────────────────────

    def _to_abs(self, rel_x: int, rel_y: int) -> tuple[int, int]:
        """窗口相对坐标 → 屏幕绝对坐标。"""
        return (
            self._window_rect.left + rel_x,
            self._window_rect.top + rel_y,
        )

    def _chat_list_bottom(self) -> int:
        if self.layout.chat_list_bottom <= 0:
            return self._window_rect.height()
        return self.layout.chat_list_bottom

    def _msg_area_right(self) -> int:
        if self.layout.msg_area_right <= 0:
            return self._window_rect.width()
        return self.layout.msg_area_right

    def _input_width(self) -> int:
        if self.layout.input_width <= 0:
            return self._window_rect.width() - self.layout.input_left - 20
        return self.layout.input_width

    # ─── 截图 ─────────────────────────────────────

    def screenshot(self) -> Image.Image:
        if not self.ensure_window():
            raise RuntimeError("WeChat window not available for screenshot")
        r = self._window_rect
        return pyautogui.screenshot(region=(r.left, r.top, r.width(), r.height()))

    def screenshot_region(self, rel_x: int, rel_y: int, w: int, h: int) -> Image.Image:
        if not self.ensure_window():
            raise RuntimeError("WeChat window not available for screenshot")
        if w <= 0 or h <= 0:
            raise ValueError(f"Screenshot region dimensions must be positive: {w}x{h}")
        abs_x, abs_y = self._to_abs(rel_x, rel_y)
        return pyautogui.screenshot(region=(abs_x, abs_y, w, h))

    def screenshot_chat_list(self) -> Image.Image:
        return self.screenshot_region(
            self.layout.chat_list_left,
            self.layout.chat_list_top,
            self.layout.chat_list_width,
            self._chat_list_bottom() - self.layout.chat_list_top,
        )

    def screenshot_message_area(self) -> Image.Image:
        return self.screenshot_region(
            self.layout.msg_area_left,
            self.layout.msg_area_top,
            self._msg_area_right() - self.layout.msg_area_left,
            self._window_rect.height() - self.layout.msg_area_bottom - self.layout.msg_area_top,
        )

    def screenshot_message_area_bottom(self, capture_height: int = 200) -> Image.Image:
        """只截消息区域底部（最新消息所在位置），大幅减少 OCR 面积。"""
        full_height = self._window_rect.height() - self.layout.msg_area_bottom - self.layout.msg_area_top
        h = min(capture_height, full_height)
        y = self.layout.msg_area_top + full_height - h
        return self.screenshot_region(
            self.layout.msg_area_left,
            y,
            self._msg_area_right() - self.layout.msg_area_left,
            h,
        )

    # ─── 鼠标操作 ─────────────────────────────────

    def _click_rel(self, rel_x: int, rel_y: int, human_like: bool = True):
        abs_x, abs_y = self._to_abs(rel_x, rel_y)
        if human_like:
            abs_x += random.randint(-3, 3)
            abs_y += random.randint(-2, 2)
        pyautogui.click(abs_x, abs_y)
        time.sleep(0.05)

    def _move_to_rel(self, rel_x: int, rel_y: int):
        abs_x, abs_y = self._to_abs(rel_x, rel_y)
        pyautogui.moveTo(abs_x, abs_y, duration=0.05)

    def click_chat_item(self, index: int):
        """点击聊天列表中的第 index 项（从 0 开始）。"""
        x = self.layout.chat_list_left + self.layout.chat_list_width // 2
        y = (self.layout.chat_list_top + self.layout.chat_item_height // 2
             + index * self.layout.chat_item_height)
        self._click_rel(x, y)
        time.sleep(0.15)

    def click_input_box(self):
        """点击输入框。"""
        x = self.layout.input_left + 30
        y = self._window_rect.height() - self.layout.input_top_offset
        self._click_rel(x, y)
        time.sleep(0.05)

    # ─── 消息读取 ─────────────────────────────────

    def _ocr_image(self, img: Image.Image) -> list[dict]:
        """对图片进行 OCR，返回检测到的文本行列表。

        Returns: [{"text": str, "box": (x1,y1,x2,y2), "confidence": float}, ...]
        """
        from paddleocr import PaddleOCR
        if not hasattr(self, '_ocr'):
            self._ocr = PaddleOCR(
                lang='ch',
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )

        # 缩小图片加速 OCR（聊天文字足够大，缩小不影响识别）
        w, h = img.size
        scale = min(1.0, 640 / max(w, h))
        if scale < 1.0:
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        img_array = np.array(img)
        result = self._ocr.predict(img_array)
        if result is None or len(result) == 0:
            return []

        items = []
        for page in result:
            texts = page.get("rec_texts", []) if isinstance(page, dict) else getattr(page, 'rec_texts', [])
            scores = page.get("rec_scores", []) if isinstance(page, dict) else getattr(page, 'rec_scores', [])
            polys = page.get("dt_polys", []) if isinstance(page, dict) else getattr(page, 'dt_polys', [])

            for i, text in enumerate(texts):
                if i >= len(polys):
                    continue
                box = polys[i]  # shape (4, 2): [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                conf = scores[i] if i < len(scores) else 0.0
                # 坐标映射回原始图片空间
                inv = 1.0 / scale if scale < 1.0 else 1.0
                items.append({
                    "text": text,
                    "box": (int(box[0][0] * inv), int(box[0][1] * inv),
                             int(box[2][0] * inv), int(box[2][1] * inv)),
                    "confidence": conf,
                })
        return items

    def get_chat_list_texts(self) -> list[dict]:
        """OCR 识别聊天列表中的文字，返回聊天项列表。"""
        img = self.screenshot_chat_list()
        items = self._ocr_image(img)

        # 按 y 坐标排序
        items.sort(key=lambda x: x["box"][1])

        # 将同一行的文本合并（聊天名可能被 OCR 拆成多段）
        merged = self._merge_text_rows(items, max_gap=15)
        return [{"name": m["text"], "y": m["y"]} for m in merged]

    def get_message_area_texts(self) -> list[dict]:
        """OCR 识别消息区域的文字，返回每条消息的文本、y 坐标和 x 起点。

        微信消息区域中：对方消息靠左 (x 较小)，自己消息靠右 (x 较大)。
        """
        img = self.screenshot_message_area()
        items = self._ocr_image(img)

        items.sort(key=lambda x: x["box"][1])

        # 按气泡分组（同一气泡内可能有多行）
        messages = self._merge_text_rows(items, max_gap=25)
        return [
            {"text": m["text"], "y": m["y"], "x": m.get("x_start", 0)}
            for m in messages
        ]

    def _merge_text_rows(self, items: list[dict], max_gap: int = 15) -> list[dict]:
        """合并垂直方向上临近的文本行。

        同时要求水平方向有重叠或接近，避免把左侧聊天名和右侧消息预览
        合并在一起。
        """
        if not items:
            return []

        merged = []
        current = {"text": items[0]["text"], "y": items[0]["box"][1],
                    "bottom": items[0]["box"][3],
                    "x_start": items[0]["box"][0], "x_end": items[0]["box"][2]}

        for item in items[1:]:
            y_gap = item["box"][1] - current["bottom"]
            # 水平方向：当前块和下一块是否有重叠或接近
            x_overlap_start = max(current["x_start"], item["box"][0])
            x_overlap_end = min(current["x_end"], item["box"][2])
            x_overlap = max(0, x_overlap_end - x_overlap_start)
            x_gap = max(item["box"][0] - current["x_end"],
                       current["x_start"] - item["box"][2])

            if y_gap < max_gap and (x_overlap > 0 or x_gap < 60):
                current["text"] += item["text"]
                current["bottom"] = item["box"][3]
                current["x_start"] = min(current["x_start"], item["box"][0])
                current["x_end"] = max(current["x_end"], item["box"][2])
            else:
                merged.append(current)
                current = {"text": item["text"], "y": item["box"][1],
                            "bottom": item["box"][3],
                            "x_start": item["box"][0], "x_end": item["box"][2]}
        merged.append(current)
        return merged

    # ─── 扫描未读 & 读取消息 ──────────────────────

    def scan_unread_chats(self) -> list[tuple[str, int]]:
        """通过对比前后两次截图，检测新出现的红色未读标记。

        策略：静态红色头像不会变，只有新出现的未读红点才会被捕获。
        """

        img = self.screenshot_chat_list()
        w, h = img.size
        logger.info(f"Chat list screenshot: {w}x{h}")

        # 保存调试截图
        debug_dir = Path(__file__).parent.parent / "debug"
        debug_dir.mkdir(exist_ok=True)
        img.save(debug_dir / "chat_list.png")

        # ── 1. 与上一次截图对比 ──
        img_arr = np.array(img, dtype=np.int16)
        if not hasattr(self, '_prev_chat_list_img'):
            # 首次运行，保存截图作为基准，下次才能检测
            self._prev_chat_list_img = img_arr
            logger.info("First run — saved baseline screenshot, will detect on next poll")
            return []

        prev = self._prev_chat_list_img
        self._prev_chat_list_img = img_arr

        if prev.shape != img_arr.shape:
            return []

        # 计算像素差异（只看红色通道的显著变化）
        diff = np.abs(img_arr - prev)
        # 关注红色通道差异大、且当前像素偏红的点
        red_changed = (diff[:, :, 0] > 30) & \
                       (img_arr[:, :, 0] > 160) & \
                       (img_arr[:, :, 0] - img_arr[:, :, 1] > 40) & \
                       (img_arr[:, :, 0] - img_arr[:, :, 2] > 40)

        changed_coords = np.argwhere(red_changed)
        logger.info(f"Changed red pixels (diff vs baseline): {len(changed_coords)}")

        if len(changed_coords) < 5:
            logger.debug("No significant red changes detected")
            return []

        # 保存 diff 调试图
        diff_img = np.zeros((h, w, 3), dtype=np.uint8)
        diff_img[red_changed] = [255, 255, 255]
        Image.fromarray(diff_img).save(debug_dir / "chat_list_diff.png")

        # ── 2. 将变化的红色像素聚类 ──
        changed_set = set((int(y), int(x)) for y, x in changed_coords)
        clusters = []

        while changed_set:
            seed = changed_set.pop()
            stack = [seed]
            min_y, min_x = seed[0], seed[1]
            max_y, max_x = seed[0], seed[1]
            count = 0

            while stack:
                py, px = stack.pop()
                count += 1
                min_y, max_y = min(min_y, py), max(max_y, py)
                min_x, max_x = min(min_x, px), max(max_x, px)

                for dy in (-2, -1, 0, 1, 2):
                    for dx in (-2, -1, 0, 1, 2):
                        if dy == 0 and dx == 0:
                            continue
                        n = (py + dy, px + dx)
                        if n in changed_set:
                            changed_set.remove(n)
                            stack.append(n)

            cw = max_x - min_x
            ch = max_y - min_y
            clusters.append((min_x, min_y, max_x, max_y, count, cw, ch))

        logger.info(f"Changed red clusters: {len(clusters)}")

        # ── 3. 过滤：未读标记特征 ──
        # 未读红点/数字徽章：宽度 8-55px，高度 8-55px，像素 30-3000
        candidates = []
        for min_x, min_y, max_x, max_y, cnt, cw, ch in clusters:
            if 6 < cw < 60 and 6 < ch < 60 and 20 < cnt < 3500:
                candidates.append((min_x, min_y, max_x, max_y, cnt))
                logger.debug(f"  Candidate: x=[{min_x}-{max_x}] y=[{min_y}-{max_y}] "
                            f"{cw}x{ch} px={cnt}")

        logger.info(f"Candidates after size filter: {len(candidates)}")

        # ── 4. 映射到聊天项索引 ──
        item_height = self.layout.chat_item_height
        unread_indices = set()
        for min_x, min_y, max_x, max_y, cnt in candidates:
            y_center = (min_y + max_y) // 2
            idx = y_center // item_height
            unread_indices.add(idx)
            logger.debug(f"  → chat index {idx} (y_center={y_center})")

        logger.info(f"Unread chat indices: {unread_indices}")

        # ── 5. OCR 获取聊天名并匹配 ──
        chat_texts = self.get_chat_list_texts()
        logger.info(f"OCR: {[(c['name'][:10], c['y']) for c in chat_texts[:20]]}")

        y_to_name: dict[int, str] = {}
        for chat in chat_texts:
            y_to_name[chat["y"] // item_height] = chat["name"]

        unread_entries: list[tuple[str, int]] = []
        for idx in sorted(unread_indices):
            name = y_to_name.get(idx)
            if name is not None:
                unread_entries.append((name, idx))
                logger.info(f"  Unread idx={idx} → {name}")
            else:
                expected_y = idx * item_height + item_height // 2
                for chat in chat_texts:
                    if abs(chat["y"] - expected_y) < item_height:
                        unread_entries.append((chat["name"], idx))
                        logger.info(f"  Unread idx={idx} → {chat['name']} (proximity)")
                        break

        return unread_entries

    def get_latest_messages(self, count: int = 5, exclude_self: bool = True) -> list[str]:
        """获取当前聊天窗口的最新消息。

        Args:
            count: 最多返回的消息条数
            exclude_self: 为 True 时过滤掉自己发的消息（靠右的绿色气泡），
                          只保留对方发的消息（靠左的白色气泡）。
        """
        # 只截底部 200px（覆盖约 3~4 条消息），count 小的时候大幅减少 OCR 面积
        capture_height = min(200 + count * 60, 600)
        img = self.screenshot_message_area_bottom(capture_height)
        items = self._ocr_image(img)
        items.sort(key=lambda x: x["box"][1])
        messages = self._merge_text_rows(items, max_gap=25)

        if exclude_self:
            msg_width = self._msg_area_right() - self.layout.msg_area_left
            mid_x = msg_width * 0.45
            messages = [m for m in messages if m.get("x_start", 0) < mid_x]
        recent = messages[-min(count, len(messages)):]
        return [m["text"] for m in recent]

    # ─── 发送消息 ─────────────────────────────────

    def send_message(self, text: str) -> bool:
        """向当前聊天发送消息（使用剪贴板粘贴，支持中文）。

        Returns True on success.
        """
        try:
            import pyperclip

            # 确保微信窗口在前台（长时间延迟后可能被其他窗口遮挡）
            if not self.ensure_window(foreground=True):
                logger.error("Cannot find WeChat window for sending")
                return False
            time.sleep(0.1)

            pyperclip.copy(text)
            logger.info(f"Sending [{text}]")

            self.click_input_box()
            time.sleep(0.05)

            # 全选清空原有内容，粘贴新内容
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)

            # 回车发送
            pyautogui.press("enter")
            logger.info("Message sent successfully")
            return True
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False

    def send_message_char_by_char(self, text: str) -> bool:
        return self.send_message(text)
