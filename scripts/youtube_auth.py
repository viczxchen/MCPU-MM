#!/usr/bin/env python3
"""
YouTube 登录态管理脚本（合并版）

子命令：
  export    手动登录并导出 storage_state（自动验证）
  verify    验证已有的 storage_state 是否有效
  use       在容器内复用 storage_state（示例代码）

示例：
  # 本机登录并自动验证
  python scripts/youtube_auth.py export

  # 验证现有登录态
  python scripts/youtube_auth.py verify --state-path playwright/.auth/youtube.json

  # 容器内使用（在容器里执行）
  python scripts/youtube_auth.py use --state-path /auth/youtube.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_VIDEO_URL = "https://www.youtube.com/watch?v=jOtDhq0erTg"
DEFAULT_AUTH_PATH = "playwright/.auth/youtube.json"
DEFAULT_VERIFY_URL = "https://www.youtube.com/feed/subscriptions"


def check_state_valid(state_path: Path, url: str, headless: bool = False, debug: bool = False) -> tuple[bool, str, dict]:
    """验证 storage_state 是否有效，返回 (is_valid, message, details)"""
    if not state_path.exists():
        return False, f"storage_state 文件不存在: {state_path}", {}

    try:
        with state_path.open("r", encoding="utf-8") as f:
            json.load(f)
    except Exception as exc:
        return False, f"无效的 JSON 文件: {exc}", {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except PlaywrightTimeoutError:
            browser.close()
            return False, "页面加载超时", {}

        current_url = page.url
        html = page.content()
        title = page.title()

        # 检查登录状态的多个指标
        # 检查是否在登录页面
        is_accounts_page = "accounts.google.com" in current_url
        
        # 检查是否有明显的"请登录"提示（这是未登录的主要标志）
        has_login_prompt = "请登录，以便我们确认你不是聊天机器人" in html or "Sign in to confirm you're not a bot" in html
        
        # 检查是否在订阅页面（登录后才能访问）
        is_subscriptions_page = "/feed/subscriptions" in current_url and "Subscriptions" in title
        
        # 检查是否有用户头像（登录后的标志）
        try:
            has_user_avatar = page.locator('button#avatar-btn, [aria-label*="channel"], ytd-topbar-menu-button-renderer #button').count() > 0
        except:
            has_user_avatar = False
        
        checks = {
            "is_accounts_page": is_accounts_page,
            "has_login_prompt": has_login_prompt,
            "is_subscriptions_page": is_subscriptions_page,
            "has_user_avatar": has_user_avatar,
            "title": title,
        }

        # 综合判断：访问了订阅页面且没有强制登录提示，认为是登录状态
        signed_in = is_subscriptions_page or (not is_accounts_page and not has_login_prompt)

        if debug:
            print(f"  [Debug] URL: {current_url}")
            print(f"  [Debug] Title: {title}")
            print(f"  [Debug] 是登录页面: {checks['is_accounts_page']}")
            print(f"  [Debug] 有登录提示: {checks['has_login_prompt']}")
            print(f"  [Debug] 是订阅页面: {checks['is_subscriptions_page']}")
            print(f"  [Debug] 有用户头像: {checks['has_user_avatar']}")

        browser.close()

        details = {"url": current_url, "title": title, **checks}

        if signed_in:
            return True, f"✓ 验证通过 (页面: {title})", details
        else:
            return False, f"✗ 未检测到登录状态 (当前: {current_url})", details


def cmd_export(args: argparse.Namespace) -> int:
    """导出登录态并自动验证"""
    state_path = Path(args.state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            slow_mo=args.slow_mo_ms,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context()
        page = context.new_page()

        print(f"[1/3] 打开页面: {args.url}")
        page.goto(args.url, wait_until="domcontentloaded")
        print("[2/3] 请在浏览器中完成 Google/YouTube 登录")
        print("      登录完成后，按回车键继续...")
        input()

        # 保存登录态
        context.storage_state(path=str(state_path))
        browser.close()

    print(f"[3/3] 已保存登录态到: {state_path}")

    # 自动验证 (使用有界面模式更可靠)
    print("\n--- 自动验证登录态 ---")
    print("提示: 验证时会弹出浏览器窗口，请等待...")
    is_valid, msg, details = check_state_valid(state_path, args.verify_url, headless=False, debug=True)
    print(msg)

    if is_valid:
        print("\n✓ 登录态导出成功且验证通过！")
        print(f"  文件位置: {state_path}")
        print(f"  验证页面: {details.get('title', 'N/A')}")
        print("  可以在容器中使用该文件：")
        print(f"    -v \"{state_path}:/auth/youtube.json:ro\"")
        return 0
    else:
        print("\n✗ 登录态验证失败")
        print("  可能原因:")
        print("  1. 浏览器中未完成完整的登录流程")
        print("  2. YouTube 要求额外的安全验证")
        print("  3. 建议直接尝试使用，可能已登录成功")
        return 1


def cmd_verify(args: argparse.Namespace) -> int:
    """验证已有的 storage_state"""
    state_path = Path(args.state_path)

    print(f"验证: {state_path}")
    is_valid, msg, details = check_state_valid(state_path, args.url, headless=args.headless, debug=True)
    print(msg)
    print(f"  页面标题: {details.get('title', 'N/A')}")
    print(f"  当前URL: {details.get('url', 'N/A')}")

    return 0 if is_valid else 1


def cmd_use(args: argparse.Namespace) -> int:
    """在容器内使用 storage_state 的示例"""
    state_path = Path(args.state_path)

    if not state_path.exists():
        print(f"[ERROR] 登录态文件不存在: {state_path}")
        print("请先在本机运行: python scripts/youtube_auth.py export")
        return 2

    print(f"使用登录态: {state_path}")
    print("示例代码（在你的脚本中使用）：")
    print(f"""
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(storage_state="{state_path}")
    page = context.new_page()
    page.goto("https://www.youtube.com/watch?v=jOtDhq0erTg")
    # ... 你的逻辑
""")

    # 可选：实际验证一下
    if args.verify:
        print("--- 验证登录态有效性 ---")
        is_valid, msg, details = check_state_valid(state_path, args.url, headless=False, debug=True)
        print(msg)
        return 0 if is_valid else 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YouTube 登录态管理脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 本机登录并自动验证（推荐）
  python scripts/youtube_auth.py export

  # 验证登录态是否还有效
  python scripts/youtube_auth.py verify

  # 在容器内使用登录态
  python scripts/youtube_auth.py use --state-path /auth/youtube.json
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # export 子命令
    export_parser = subparsers.add_parser("export", help="手动登录并导出 storage_state")
    export_parser.add_argument(
        "--url",
        default=DEFAULT_VIDEO_URL,
        help=f"初始页面 URL (default: {DEFAULT_VIDEO_URL})",
    )
    export_parser.add_argument(
        "--state-path",
        default=DEFAULT_AUTH_PATH,
        help=f"输出文件路径 (default: {DEFAULT_AUTH_PATH})",
    )
    export_parser.add_argument(
        "--verify-url",
        default=DEFAULT_VERIFY_URL,
        help=f"用于验证的 URL (default: {DEFAULT_VERIFY_URL})",
    )
    export_parser.add_argument(
        "--slow-mo-ms",
        type=int,
        default=80,
        help="慢动作延迟毫秒数",
    )
    export_parser.set_defaults(func=cmd_export)

    # verify 子命令
    verify_parser = subparsers.add_parser("verify", help="验证已有的 storage_state")
    verify_parser.add_argument(
        "--state-path",
        default=DEFAULT_AUTH_PATH,
        help=f"storage_state 文件路径 (default: {DEFAULT_AUTH_PATH})",
    )
    verify_parser.add_argument(
        "--url",
        default=DEFAULT_VERIFY_URL,
        help=f"验证页面 URL (default: {DEFAULT_VERIFY_URL})",
    )
    verify_parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="使用无头模式验证 (默认使用有界面模式更可靠)",
    )
    verify_parser.set_defaults(func=cmd_verify)

    # use 子命令
    use_parser = subparsers.add_parser("use", help="在容器内使用 storage_state")
    use_parser.add_argument(
        "--state-path",
        default="/auth/youtube.json",
        help=f"容器内的登录态文件路径 (default: /auth/youtube.json)",
    )
    use_parser.add_argument(
        "--url",
        default=DEFAULT_VERIFY_URL,
        help="验证页面 URL",
    )
    use_parser.add_argument(
        "--verify",
        action="store_true",
        help="同时验证登录态是否有效",
    )
    use_parser.set_defaults(func=cmd_use)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
