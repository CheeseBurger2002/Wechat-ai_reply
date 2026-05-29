"""诊断脚本：探测微信 4.1.10 的 UIA 控件树结构。"""
import uiautomation as auto


def print_tree(control, depth=0, max_depth=3):
    """递归打印控件树。"""
    if depth > max_depth:
        return
    try:
        name = control.Name or ""
        class_name = control.ClassName or ""
        control_type = control.ControlTypeName or ""
        auto_id = control.AutomationId or ""

        indent = "  " * depth
        info_parts = []
        if name:
            info_parts.append(f"Name='{name}'")
        if class_name:
            info_parts.append(f"Class={class_name}")
        if control_type:
            info_parts.append(f"Type={control_type}")
        if auto_id:
            info_parts.append(f"AutoId='{auto_id}'")

        line = f"{indent}{' | '.join(info_parts)}"
        if line.strip():
            print(line)
    except Exception:
        return

    try:
        children = control.GetChildren()
        for child in children:
            print_tree(child, depth + 1, max_depth)
    except Exception:
        pass


def main():
    print("=" * 60)
    print("WeChat UIA 诊断工具 (4.1.10)")
    print("=" * 60)

    # 微信 4.1.10 使用 Qt5，窗口类名为 Qt51514QWindowIcon
    print("\n[1] 查找微信窗口 (Class=Qt51514QWindowIcon)...")
    wechat = auto.WindowControl(Name="微信", ClassName="Qt51514QWindowIcon")
    if not wechat.Exists(maxSearchSeconds=3):
        wechat = auto.WindowControl(ClassName="Qt51514QWindowIcon")
        if not wechat.Exists(maxSearchSeconds=3):
            print("❌ 未找到，请确保微信已登录且窗口可见")
            return

    print(f"✅ 找到: Name='{wechat.Name}', Class={wechat.ClassName}")

    # 打印完整控件树
    print(f"\n[2] 微信窗口控件树 (深度限制 3 层):")
    print("-" * 40)
    print_tree(wechat, depth=0, max_depth=3)

    # 深层搜索关键控件
    print("\n" + "=" * 60)
    print("[3] 深层搜索关键控件 (不限深度):")
    print("-" * 40)

    # EditControl
    all_edits = []

    def find_edits(ctrl, d=0):
        if d > 10:
            return
        try:
            if ctrl.ControlTypeName == "EditControl":
                all_edits.append((ctrl, d))
            for c in ctrl.GetChildren():
                find_edits(c, d + 1)
        except:
            pass

    find_edits(wechat)
    print(f"EditControl (输入框) 共 {len(all_edits)} 个:")
    for e, d in all_edits[:15]:
        print(f"  [depth={d}] Name='{e.Name}', Class={e.ClassName}, AutoId='{e.AutomationId}'")

    # ListControl
    all_lists = []

    def find_lists(ctrl, d=0):
        if d > 10:
            return
        try:
            if ctrl.ControlTypeName in ("ListControl", "List"):
                children = []
                try:
                    children = ctrl.GetChildren() or []
                except:
                    pass
                all_lists.append((ctrl, len(children), d))
            for c in ctrl.GetChildren():
                find_lists(c, d + 1)
        except:
            pass

    find_lists(wechat)
    print(f"\nListControl 共 {len(all_lists)} 个:")
    for lst, cnt, d in all_lists[:20]:
        print(f"  [depth={d}] Name='{lst.Name}', AutoId='{lst.AutomationId}', 子项数={cnt}")

    # ButtonControl
    all_buttons = []

    def find_buttons(ctrl, d=0):
        if d > 10:
            return
        try:
            if ctrl.ControlTypeName == "ButtonControl":
                all_buttons.append((ctrl, d))
            for c in ctrl.GetChildren():
                find_buttons(c, d + 1)
        except:
            pass

    find_buttons(wechat)
    print(f"\nButtonControl 共 {len(all_buttons)} 个:")
    for b, d in all_buttons[:20]:
        print(f"  [depth={d}] Name='{b.Name}', AutoId='{b.AutomationId}'")

    # TextControl 查找聊天列表项
    all_texts = []

    def find_texts(ctrl, d=0):
        if d > 8:
            return
        try:
            if ctrl.ControlTypeName == "TextControl" and ctrl.Name:
                all_texts.append((ctrl, d))
            for c in ctrl.GetChildren():
                find_texts(c, d + 1)
        except:
            pass

    find_texts(wechat)
    print(f"\nTextControl (有名称的) 共 {len(all_texts)} 个:")
    for t, d in all_texts[:30]:
        print(f"  [depth={d}] Name='{t.Name}'")

    print("\n" + "=" * 60)
    print("诊断完成。")
    print("=" * 60)


if __name__ == "__main__":
    main()
