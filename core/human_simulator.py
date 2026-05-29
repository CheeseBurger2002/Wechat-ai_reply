import random
import time
import logging

logger = logging.getLogger("wx_reply")


class HumanSimulator:
    """模拟人类打字行为和操作节奏。"""

    def __init__(self, config: dict):
        self.reply_delay_min = config.get("reply_delay_min", 10)
        self.reply_delay_max = config.get("reply_delay_max", 60)
        self.char_delay_min = config.get("char_delay_min", 0.05)
        self.char_delay_max = config.get("char_delay_max", 0.2)
        self.pause_threshold = config.get("pause_threshold", 15)
        self.pause_delay_min = config.get("pause_delay_min", 0.5)
        self.pause_delay_max = config.get("pause_delay_max", 2.0)
        self.thinking_pause_prob = config.get("thinking_pause_probability", 0.15)
        self.thinking_pause_min = config.get("thinking_pause_min", 1.0)
        self.thinking_pause_max = config.get("thinking_pause_max", 3.0)

    def pre_reply_delay(self) -> float:
        """回复前等待一段随机时间（正偏态分布）。"""
        delay = random.betavariate(2, 5) * self.reply_delay_max
        delay = max(self.reply_delay_min, min(delay, self.reply_delay_max))
        logger.debug(f"Pre-reply delay: {delay:.1f}s")
        return delay

    def char_interval(self) -> float:
        """单字符输入间隔。"""
        return random.uniform(self.char_delay_min, self.char_delay_max)

    def should_pause(self, char_count: int) -> bool:
        return char_count > 0 and char_count % self.pause_threshold == 0

    def pause_duration(self) -> float:
        return random.uniform(self.pause_delay_min, self.pause_delay_max)

    def should_think(self) -> bool:
        return random.random() < self.thinking_pause_prob

    def thinking_duration(self) -> float:
        return random.uniform(self.thinking_pause_min, self.thinking_pause_max)

    def type_char(self, char: str):
        """输入单个字符（由 main 调用 pyautogui.write 实现）。"""
        import pyautogui
        pyautogui.write(char, interval=0.0)

    def type_text(self, text: str) -> None:
        """逐字输入文本，模拟真人打字节奏。"""
        logger.info(f"Typing {len(text)} chars...")
        for i, char in enumerate(text):
            self.type_char(char)
            delay = self.char_interval()
            time.sleep(delay)

            if self.should_pause(i + 1):
                pause = self.pause_duration()
                logger.debug(f"Sentence pause: {pause:.1f}s")
                time.sleep(pause)

            if self.should_think():
                think = self.thinking_duration()
                logger.debug(f"Thinking pause: {think:.1f}s")
                time.sleep(think)

        logger.info("Typing complete")
