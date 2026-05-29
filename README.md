# WeChat AI Auto-Reply

基于截图 + OCR + 坐标点击的微信 PC 端 AI 自动回复工具。纯模拟人类操作，不碰微信进程。

## 原理

```
微信窗口 → 截图 → OCR 识别 → AI 生成回复 → 模拟键盘粘贴发送
```

每隔几秒截取聊天列表，通过像素差异检测新的未读消息，OCR 获取消息内容，调用 AI 生成回复，最后模拟人类打字发送。

## 环境要求

- Windows 10/11
- Python 3.11+
- [Ollama](https://ollama.com)（本地模型）或 OpenAI API Key
- PC 微信（登录状态）

## 安装

```bash
git clone https://github.com/CheeseBurger2002/Wechat-ai_reply.git
cd Wechat-ai_reply
pip install -r requirements.txt
```

## 配置

编辑 [config.yaml](config.yaml)：

```yaml
ai:
  engine: ollama          # ollama 或 openai
  ollama:
    base_url: http://localhost:11434
    model: frob/qwen3.5-instruct:9b    # 非思考版，回复快
    max_tokens: 512
    temperature: 0.7
  system_prompt: '你是我的微信代聊助手...'

filters:
  blocked_keywords:       # 不回复这些人/号
    - 微信支付
    - 腾讯新闻
    - 订阅号
    - 服务号
    - 文件传输助手
    - 折叠的聊天
  trigger_keywords: []    # 留空 = 回复所有消息；填了只回复含关键词的
```

## 使用

```bash
python main.py
```

首次运行建议先用校准工具，确保坐标匹配你的微信窗口布局：

```bash
python calibrate.py
```

按照提示依次点击微信窗口中的几个关键位置，会自动更新 `config.yaml` 中的布局参数。

## 文件结构

```
├── main.py          # 主循环
├── calibrate.py     # 布局校准工具
├── config.yaml      # 配置文件
├── requirements.txt
├── core/
│   ├── wechat_controller.py  # 微信窗口截图/OCR/点击
│   ├── ai_engine.py          # AI 回复引擎
│   ├── human_simulator.py    # 模拟人类行为（延迟、打字速度）
│   └── scheduler.py          # 回复频控
└── utils/
    ├── config_loader.py
    └── logger.py
```
