"""校准工具：测量微信窗口各区域坐标，并更新 config.yaml。

使用方法：
  1. 打开并登录 PC 微信
  2. 运行 python calibrate.py
  3. 将鼠标依次移动到以下位置，按 Enter 记录：
     - 聊天列表第一个聊天项的中心
     - 聊天列表最后一个可见聊天项的中心
     - 输入框中心
     - 消息区域左上角
     - 消息区域右下角（输入框上方）
  4. 自动计算布局参数并更新 config.yaml
"""

import sys
import time
from pathlib import Path
import pyautogui
import yaml
import uiautomation as auto

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def get_wechat_rect():
    wechat = auto.WindowControl(Name="微信", ClassName="Qt51514QWindowIcon")
    if not wechat.Exists(maxSearchSeconds=3):
        wechat = auto.WindowControl(ClassName="Qt51514QWindowIcon")
        if not wechat.Exists(maxSearchSeconds=3):
            return None
 
    return wechat.BoundingRectangle


def wait_for_click(prompt: str) -> tuple[int, int]:
    """等待用户输入 Enter，记录当前鼠标位置。"""
    input(f"\n{prompt}\n  移动鼠标到目标位置后按 Enter...")
    x, y = pyautogui.position()
    print(f"  记录: ({x}, {y})")
    return x, y


def main():
    print("=" * 50)
    print("微信窗口布局校准工具")
    print("=" * 50)

    rect = get_wechat_rect()
    if rect is None:
        print("❌ 找不到微信窗口！请确保微信已打开并登录。")
        sys.exit(1)

    W_left, W_top = rect.left, rect.top
    W_width, W_height = rect.width(), rect.height()
    print(f"\n微信窗口: 左上角({W_left}, {W_top}), {W_width}x{W_height}")

    # 截图
    screenshot = pyautogui.screenshot(region=(W_left, W_top, W_width, W_height))
    screenshot.save(Path(__file__).parent / "calibration_screenshot.png")
    print("截图已保存: calibration_screenshot.png")

    def to_rel(abs_x, abs_y):
        return (abs_x - W_left, abs_y - W_top)

    print("\n" + "-" * 40)
    print("请在以下步骤中将鼠标移动到指定位置后按 Enter")
    print("提示：打开 calibration_screenshot.png 作为参考")
    print("-" * 40)

    # 1. 第一个聊天项中心
    ax, ay = wait_for_click("【步骤 1/5】第一个聊天项的中心位置")
    chat1_x, chat1_y = to_rel(ax, ay)
    print(f"  → 相对坐标: ({chat1_x}, {chat1_y})")

    # 2. 最后一个可见聊天项中心
    ax, ay = wait_for_click("【步骤 2/5】最后一个可见聊天项的中心位置")
    chatN_x, chatN_y = to_rel(ax, ay)
    print(f"  → 相对坐标: ({chatN_x}, {chatN_y})")

    # 3. 输入框中心
    ax, ay = wait_for_click("【步骤 3/5】输入框中心")
    input_x, input_y = to_rel(ax, ay)
    print(f"  → 相对坐标: ({input_x}, {input_y})")

    # 4. 消息区域左上角
    ax, ay = wait_for_click("【步骤 4/5】消息区域左上角")
    msg_left, msg_top = to_rel(ax, ay)
    print(f"  → 相对坐标: ({msg_left}, {msg_top})")

    # 5. 消息区域右下角（输入框上方）
    ax, ay = wait_for_click("【步骤 5/5】消息区域右下角（输入框上方）")
    msg_right, msg_bottom = to_rel(ax, ay)
    print(f"  → 相对坐标: ({msg_right}, {msg_bottom})")

    # 计算参数
    # 聊天列表宽度 = 第一个聊天项的 x + 一个合理偏移
    chat_list_width = msg_left  # 消息区起始 = 聊天列表宽度
    chat_list_left = 0
    chat_list_top = min(chat1_y, chatN_y)  # 列表顶部

    # 聊天项高度
    # 假设从第1个到最后1个，中间有 N-1 个间隔
    # 需要用户告知可见范围内有几个聊天项
    try:
        n_items = int(input("\n可见范围内大概有几个聊天项？(输入数字): "))
    except ValueError:
        n_items = 10
    if n_items < 2:
        n_items = 10

    chat_item_height = abs(chatN_y - chat1_y) / (n_items - 1)

    # 输入框
    input_top_offset = W_height - input_y

    # 消息区域
    msg_area_bottom = W_height - msg_bottom

    layout = {
        "chat_list_left": chat_list_left,
        "chat_list_top": chat_list_top,
        "chat_list_width": chat_list_width,
        "chat_item_height": int(round(chat_item_height)),
        "msg_area_left": msg_left,
        "msg_area_top": msg_top,
        "msg_area_bottom": msg_area_bottom,
        "input_left": msg_left + 10,
        "input_top_offset": input_top_offset,
    }

    print("\n" + "=" * 50)
    print("计算的布局参数:")
    print("=" * 50)
    for k, v in layout.items():
        print(f"  {k}: {v}")

    # 写入 config.yaml
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if config is None:
            config = {}
        if "wechat" not in config:
            config["wechat"] = {}
        config["wechat"]["layout"] = layout

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False,
                      sort_keys=False)
        print("\n✅ 布局参数已写入 config.yaml")
    except Exception as e:
        print(f"\n❌ 写入 config.yaml 失败: {e}")
        print("请手动将以上参数复制到 config.yaml 的 wechat.layout 中")


if __name__ == "__main__":
    main()
