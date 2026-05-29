import logging
from typing import Optional
from openai import OpenAI

logger = logging.getLogger("wx_reply")


class AIEngine:
    """AI 回复引擎，支持 OpenAI API 和本地 Ollama。"""

    def __init__(self, config: dict):
        engine = config.get("engine", "openai")
        self.engine = engine

        if engine == "openai":
            openai_cfg = config.get("openai", {})
            self._client = OpenAI(
                api_key=openai_cfg.get("api_key", ""),
                base_url=openai_cfg.get("base_url", "https://api.openai.com/v1"),
                timeout=30.0,
            )
            self._model = openai_cfg.get("model", "gpt-4o-mini")
            self._max_tokens = openai_cfg.get("max_tokens", 200)
            self._temperature = openai_cfg.get("temperature", 0.8)

        elif engine == "ollama":
            ollama_cfg = config.get("ollama", {})
            self._client = OpenAI(
                api_key="ollama",
                base_url=ollama_cfg.get("base_url", "http://localhost:11434") + "/v1",
                timeout=30.0,
            )
            self._model = ollama_cfg.get("model", "qwen2.5:7b")
            self._max_tokens = ollama_cfg.get("max_tokens", 200)
            self._temperature = ollama_cfg.get("temperature", 0.8)

        else:
            raise ValueError(f"Unknown AI engine: {engine}")

        self._system_prompt = config.get("system_prompt", "你是一个友好的助手。")
        self._conversation_history: dict[str, list[dict]] = {}

    def generate_reply(self, contact: str, incoming_message: str) -> Optional[str]:
        """根据收到的消息生成回复。

        Args:
            contact: 联系人名称
            incoming_message: 收到的消息内容

        Returns:
            生成的回复文本，失败返回 None
        """
        if contact not in self._conversation_history:
            self._conversation_history[contact] = []

        history = self._conversation_history[contact]

        # 保留最近 10 轮对话作为上下文
        if len(history) > 20:
            history = history[-20:]
            self._conversation_history[contact] = history

        messages = [
            {"role": "system", "content": self._system_prompt},
            *history,
            {"role": "user", "content": incoming_message},
        ]

        for attempt in (1, 2):
            try:
                tokens = self._max_tokens if attempt == 1 else self._max_tokens * 2
                logger.debug(f"Calling {self._model} (attempt {attempt}, max_tokens={tokens}): {incoming_message[:80]}")
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    max_tokens=tokens,
                    temperature=self._temperature,
                )
                reply = response.choices[0].message.content
                finish = response.choices[0].finish_reason

                if reply and reply.strip():
                    history.append({"role": "user", "content": incoming_message})
                    history.append({"role": "assistant", "content": reply})
                    self._conversation_history[contact] = history
                    logger.info(f"AI reply generated for {contact}: {reply[:40]}...")
                    return reply

                # Empty reply — retry once with double tokens if truncated
                logger.warning(
                    f"AI returned empty reply for {contact}. "
                    f"finish_reason={finish}, model={self._model}"
                )
                if finish != "length":
                    break  # not a truncation issue, don't retry

            except Exception as e:
                logger.error(f"AI generation failed (attempt {attempt}): {e}")
                if attempt == 2:
                    return None

        # Record the incoming message even if reply failed
        history.append({"role": "user", "content": incoming_message})
        self._conversation_history[contact] = history
        return None

    def clear_history(self, contact: str):
        """清除与指定联系人的对话历史。"""
        self._conversation_history.pop(contact, None)
