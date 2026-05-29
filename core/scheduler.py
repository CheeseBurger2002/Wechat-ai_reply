import time
import random
import logging
from datetime import datetime

logger = logging.getLogger("wx_reply")


class Scheduler:
    """作息调度和频控。"""

    def __init__(self, config: dict):
        self.enabled = config.get("enabled", True)
        self.work_start = config.get("work_start", 8)
        self.work_end = config.get("work_end", 23)
        self.per_contact_cooldown = config.get("per_contact_cooldown", 120)
        self._last_reply_time: dict[str, float] = {}

    def is_working_hours(self) -> bool:
        """检查当前是否在工作时间内。"""
        if not self.enabled:
            return True
        hour = datetime.now().hour
        return self.work_start <= hour < self.work_end

    def can_reply(self, contact: str) -> bool:
        """检查是否可以回复该联系人（频控）。

        is_working_hours 由调用方（main.py）统一检查，此处只做频控。"""
        last_time = self._last_reply_time.get(contact, 0)
        elapsed = time.time() - last_time
        if elapsed < self.per_contact_cooldown:
            logger.debug(
                f"Cooldown for {contact}: {self.per_contact_cooldown - elapsed:.0f}s remaining"
            )
            return False

        return True

    def record_reply(self, contact: str):
        """记录一次回复。"""
        self._last_reply_time[contact] = time.time()

    def random_sleep_until_next_poll(self, min_sec: float, max_sec: float):
        """随机等待一段时间再轮询。"""
        delay = random.uniform(min_sec, max_sec)
        logger.debug(f"Next poll in {delay:.1f}s")
        time.sleep(delay)
