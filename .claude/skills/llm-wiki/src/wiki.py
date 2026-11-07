#!/usr/bin/env python3
"""llm-wiki 独立 CLI：把归档 Markdown 编译成交叉链接的知识百科。

自包含：只 import 本技能 src/ 下的 ``wiki_tool`` 副本与第三方 pip 库，
不依赖 BookerMarkdownTool 包，也不依赖当前工作目录。

用法（任意 cwd）：

    python <本文件绝对路径> <wiki_dir> [选项]
"""

import argparse
import os
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from wiki_tool.md2wiki import md2wiki  # noqa: E402


def _utf8_stdio() -> None:
    """Windows 控制台默认非 UTF-8，日志输出中文时容易乱码。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    openai_key = os.environ.get('OPENAI_API_KEY')
    openai_url = os.environ.get('OPENAI_BASE_URL')
    openai_model = os.environ.get('OPENAI_CHAT_MODEL', 'gpt-3.5-turbo')
    default_categories = os.environ.get('WIKI_CATEGORIES')

    p = argparse.ArgumentParser(
        prog="llm-wiki",
        description="将归档 Markdown 源码编译为交叉链接的知识百科",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── wiki 参数 ────────────────────────────────────────
    p.add_argument("wiki_dir", help="wiki 目录（含 sources/pages/index），若不存在则新建")
    p.add_argument(
        "-c", "--max-chars", type=int, default=35_000,
        help="单次提示中原文长度上限（默认 35000）",
    )
    p.add_argument(
        "-l", "--limit", type=int, default=None,
        help="本次最多编译的归档源数量",
    )
    p.add_argument(
        "-f", "--fix", action='store_true',
        help="在摄取完毕后执行坏链修复",
    )
    p.add_argument("-i", "--input-dir", help="要添加的 MD 文件或者目录")
    p.add_argument(
        "--categories", default=default_categories,
        help="逗号分隔的分类列表；缺省使用内置 5 类（也可用环境变量 WIKI_CATEGORIES）",
    )

    # ── 全局 LLM 参数（与原 BookerMarkdownTool 全局选项对齐）──
    p.add_argument("-m", "--model", default=openai_model, help="模型名称")
    p.add_argument("-k", "--key", default=openai_key, help="OpenAI API Key")
    p.add_argument("-r", "--retry", type=int, default=1_000_000, help="重试次数")
    p.add_argument("-tm", "--temp", type=float, default=1, help="温度")
    p.add_argument("-tp", "--top-p", type=float, help="top-p")
    p.add_argument("-fp", "--frequency-penalty", type=float, help="频率惩罚")
    p.add_argument("-pp", "--presence-penalty", type=float, help="存在惩罚")
    p.add_argument("-mt", "--max-tokens", type=int, default=None, help="最大 token 数")
    p.add_argument("-H", "--host", default=openai_url, help="API 地址（如 https://host/v1）")
    p.add_argument(
        "-ua", "--user-agent", default='claude-cli/2.1.41 (external, cli)',
        help="HTTP User-Agent 请求头",
    )
    p.add_argument("-ST", "--no-stream", action='store_true', help="关闭流式输出模式")
    p.add_argument("-eb", "--extra-body", help="额外请求体（JSON 字符串）")
    p.add_argument("-ct", "--conn-timeout", type=int, default=60, help="连接超时秒数")
    p.add_argument("-rt", "--read-timeout", type=int, default=120, help="读取超时秒数")
    p.add_argument("-rr", "--repetition-regex", default='', help="重复检测正则")
    p.add_argument("-TN", "--no-think", action='store_true', help="关闭思考模式")
    p.add_argument("-D", "--debug", action='store_true', help="调试模式")
    return p


def main(argv=None) -> None:
    _utf8_stdio()
    args = build_parser().parse_args(argv)
    md2wiki(args)


if __name__ == "__main__":
    main()
