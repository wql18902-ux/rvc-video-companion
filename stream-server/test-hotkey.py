#!/usr/bin/env python3
"""
RVC 全局热键检测脚本
运行后按 A / S / D，看是否能被捕获
如果显示「无权限」，需要去 系统设置 → 隐私与安全性 → 辅助功能 → 添加终端
"""
import time
import sys

try:
    from pynput import keyboard
except ImportError:
    print("❌ 未安装 pynput，运行: pip3 install pynput")
    sys.exit(1)

events = []

def on_press(key):
    try:
        if hasattr(key, 'char') and key.char in ('s', 'S'):
            events.append('S(暂停/播放)')
        elif hasattr(key, 'char') and key.char in ('a', 'A'):
            events.append('A(后退1秒)')
        elif hasattr(key, 'char') and key.char in ('d', 'D'):
            events.append('D(前进1秒)')
    except Exception:
        pass
    if len(events) >= 3:
        return False

print("=" * 50)
print("  🔑 RVC 全局热键检测")
print("  请在 5 秒内依次按: A → S → D")
print("=" * 50)

with keyboard.Listener(on_press=on_press) as listener:
    listener.join(timeout=5)

if events:
    print(f"✅ 捕获成功 ({len(events)} 个):", ", ".join(events))
    print("   全局热键可用，启动服务器后 A/D/S 在任何窗口都生效")
else:
    print("❌ 未捕获到任何按键")
    print("   可能原因：")
    print("   1. 终端/IDE 没有辅助功能权限")
    print("   2. 按的不是 A/D/S")
    print()
    print("   修复方法：")
    print("   系统设置 → 隐私与安全性 → 辅助功能")
    print("   把运行服务器的终端/IDE 加进去，重新启动")
