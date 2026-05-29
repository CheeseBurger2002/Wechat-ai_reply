"""
WeChat AI Auto-Reply — 基于截图+OCR+坐标点击的微信 AI 自动回复工具。
纯模拟人类操作：看屏幕→识别文字→点鼠标→敲键盘，不碰微信进程。
"""

import time
import random
import logging
import signal
import sys

from utils.config_loader import load_config
from utils.logger import setup_logger
from core.wechat_controller import WeChatController, WeChatLayout
from core.ai_engine import AIEngine
from core.human_simulator import HumanSimulator
from core.scheduler import Scheduler

logger: logging.Logger = None  # type: ignore
_running = True


def signal_handler(sig, frame):
    global _running
    logger.info("Shutting down...")
    _running = False


def is_chat_blocked(chat_name: str, blocked_keywords: list[str]) -> bool:
    return any(kw in chat_name for kw in blocked_keywords)


def layout_from_config(cfg: dict) -> WeChatLayout:
    from dataclasses import fields
    valid = {f.name for f in fields(WeChatLayout)}
    filtered = {k: v for k, v in cfg.get("layout", {}).items() if k in valid}
    return WeChatLayout(**filtered)


def run():
    global logger

    config = load_config()
    logger = setup_logger("wx_reply", logging.DEBUG)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 50)
    logger.info("WeChat AI Auto-Reply starting...")
    logger.info("=" * 50)

    # 初始化模块
    layout = layout_from_config(config.wechat)
    wechat = WeChatController(layout=layout)
    ai = AIEngine(config.ai)
    human = HumanSimulator(config.human)
    scheduler = Scheduler(config.schedule)

    blocked_keywords = config.filters.get("blocked_keywords", [])
    trigger_keywords = config.filters.get("trigger_keywords", [])
    poll_min = config.wechat.get("poll_interval_min", 10)
    poll_max = config.wechat.get("poll_interval_max", 20)

    # 查找微信窗口
    if not wechat.find_window():
        logger.error("Please open & login to WeChat PC first!")
        return

    logger.info("Ready. Monitoring for new messages...")
    logger.info("Press Ctrl+C to stop.")

    prev_unread_names = set()
    sent_messages: dict[str, str] = {}  # contact → last reply text

    while _running:
        try:
            logger.debug("Polling cycle start...")
            if not wechat.ensure_window():
                logger.warning("WeChat window lost, retrying...")
                time.sleep(5)
                continue

            # 扫描未读聊天：对比上一轮，只有新出现的未读才算
            unread_entries = wechat.scan_unread_chats()
            logger.info(f"Unread chat entries: {unread_entries}")
            unread_set = {name for name, _ in unread_entries}
            new_unread = [(n, i) for n, i in unread_entries if n not in prev_unread_names]
            prev_unread_names = unread_set
            logger.info(f"New unread: {[n for n, _ in new_unread]}")

            if not new_unread:
                logger.debug("No new unread messages, waiting...")

            for chat_name, chat_idx in new_unread:
                if not _running:
                    break

                if is_chat_blocked(chat_name, blocked_keywords):
                    logger.debug(f"Blocked: {chat_name}")
                    continue

                if not scheduler.can_reply(chat_name):
                    prev_unread_names.discard(chat_name)
                    continue

                logger.info(f"New message from: [{chat_name}]")

                wechat.click_chat_item(chat_idx)
                time.sleep(0.15)

                messages = wechat.get_latest_messages(count=1, exclude_self=True)
                if not messages:
                    logger.debug(f"No messages readable in chat: {chat_name}")
                    continue

                incoming = messages[-1]

                # 如果这条消息和我们上次回复的相同，说明没有新的对方消息
                if chat_name in sent_messages and incoming == sent_messages[chat_name]:
                    logger.debug(f"Skipping own reply: {incoming[:30]}...")
                    continue

                # 检查触发关键词
                if trigger_keywords and not any(kw in incoming for kw in trigger_keywords):
                    logger.debug(f"Not triggered: {incoming[:30]}...")
                    continue

                logger.info(f"Message: {incoming[:60]}...")

                # AI 生成回复
                reply = ai.generate_reply(chat_name, incoming)
                if reply is None:
                    logger.warning("AI failed to generate reply")
                    continue

                logger.info(f"Reply text: {reply}")

                # 回复前延迟
                pre_delay = human.pre_reply_delay()
                logger.info(f"Waiting {pre_delay:.1f}s before replying...")
                time.sleep(pre_delay)

                if not _running:
                    break

                # 发送消息
                if not wechat.send_message(reply):
                    logger.error("Failed to send message")
                    continue

                sent_messages[chat_name] = reply
                scheduler.record_reply(chat_name)
                # 回复后从 prev 中移除，这样对方如果再发新消息能被检测到
                prev_unread_names.discard(chat_name)
                logger.info(f"Replied to [{chat_name}]: {reply[:40]}...")

            # 随机间隔后再次轮询
            scheduler.random_sleep_until_next_poll(poll_min, poll_max)

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    run()
