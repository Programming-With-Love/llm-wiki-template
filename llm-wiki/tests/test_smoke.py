#!/usr/bin/env python3
"""llm-wiki 离线冒烟测试：不发起任何网络请求。

用固定返回的 StubAgent 替换真实 LLM 代理，验证完整编排流程与纯函数行为。
"""

import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = SKILL_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from wiki_tool import md2wiki as m  # noqa: E402
from wiki_tool.md2wiki_models import WikiPagePlan, WikiFixDecision  # noqa: E402
from wiki_tool.util import render_prompt, ext_code_block, ext_cont_block  # noqa: E402


def make_args(wiki_dir, **kw):
    base = dict(
        wiki_dir=str(wiki_dir),
        max_chars=35_000,
        limit=None,
        fix=False,
        input_dir=None,
        categories="cat1",
        model="stub-model",
        key="stub-key",
        host=None,
        retry=1,
        temp=1,
        top_p=None,
        frequency_penalty=None,
        presence_penalty=None,
        max_tokens=None,
        user_agent="test-agent",
        no_stream=True,
        extra_body=None,
        conn_timeout=60,
        read_timeout=120,
        repetition_regex="",
        no_think=False,
        debug=False,
    )
    base.update(kw)
    return Namespace(**base)


class StubAgent:
    def plan_pages(self, **kw):
        return [WikiPagePlan(
            file="alpha.md", action="create", focus="测试主题",
            category="cat1", tags=["t1"],
        )]

    def write_page(self, **kw):
        return (
            "---\n"
            "title: Alpha\n"
            "description: 自动生成的测试页\n"
            "category: cat1\n"
            "tags:\n- t1\n"
            "---\n"
            "## 概览\n\n参见 [[missing]]。\n"
        )

    def fix_wikilinks(self, **kw):
        return [WikiFixDecision(target="missing", action="drop", to="")]


class UtilTest(unittest.TestCase):
    def test_render_prompt_keeps_unknown(self):
        out = render_prompt("a={a} b={b}", a="1")
        self.assertEqual(out, "a=1 b={b}")

    def test_extractors(self):
        self.assertEqual(ext_code_block("```json\n{\"a\":1}\n```"), "\n{\"a\":1}\n")
        self.assertEqual(ext_cont_block("[content]hi[/content]"), "hi")

    def test_front_roundtrip_crlf(self):
        text = "---\r\ntitle: T\r\ndate: 2026-01-01\r\n---\r\nbody\r\n"
        meta, body = m._parse_front(text)
        self.assertEqual(meta["title"], "T")
        self.assertEqual(body.strip(), "body")
        # dump 后再解析仍可往返
        meta2, body2 = m._parse_front(m._dump_front(meta, body))
        self.assertEqual(meta2["title"], "T")

    def test_split_source_body(self):
        summary, content = m._split_source_body(
            "## 摘要\n\nS\n\n## 原文\n\nC\n"
        )
        self.assertEqual(summary, "S")
        self.assertEqual(content, "C")

    def test_normalize_categories(self):
        self.assertEqual(m._normalize_categories(None), m.DEFAULT_CATEGORIES)
        self.assertEqual(
            m._normalize_categories("a，b, a; c"), ["a", "b", "c"]
        )
        with self.assertRaises(SystemExit):
            m._normalize_categories("bad/name")

    def test_apply_fix(self):
        self.assertEqual(
            m.Md2WikiOrchestrator._apply_fix("x [[t|别名]] y", "t", "drop"),
            "x 别名 y",
        )
        self.assertEqual(
            m.Md2WikiOrchestrator._apply_fix("x [[t]] y", "t", "drop"),
            "x t y",
        )
        self.assertEqual(
            m.Md2WikiOrchestrator._apply_fix("x [[t]] y", "t", "rename", "n"),
            "x [[n]] y",
        )


class OrchestratorTest(unittest.TestCase):
    def test_end_to_end_offline(self):
        with tempfile.TemporaryDirectory() as td:
            wiki = Path(td) / "wiki"
            src_dir = wiki / "sources" / "2026" / "01"
            src_dir.mkdir(parents=True)
            src = src_dir / "a.md"
            src.write_text(
                "---\r\n"
                "title: 源A\r\n"
                "source: 站点\r\n"
                "url: https://example.com/a\r\n"
                "date: 2026-01-01\r\n"
                "---\r\n"
                "## 摘要\r\n\r\n摘要内容\r\n\r\n"
                "## 原文\r\n\r\n正文内容\r\n",
                encoding="utf8",
            )

            args = make_args(wiki, fix=True)
            orch = m.Md2WikiOrchestrator(args)
            orch.agent = StubAgent()
            count = orch.run()

            self.assertEqual(count, 1)

            page = wiki / "pages" / "alpha.md"
            self.assertTrue(page.exists())
            page_text = page.read_text(encoding="utf8")
            self.assertIn("## 来源", page_text)
            self.assertIn("../sources/2026/01/a.md", page_text)
            self.assertIn("参见 missing。", page_text)  # drop 生效

            src_meta, _ = m._parse_front(src.read_text(encoding="utf8"))
            self.assertTrue(src_meta["compiled"])
            self.assertEqual(src_meta["pages"], ["alpha.md"])

            self.assertTrue((wiki / "index.md").exists())
            self.assertIn("[[alpha]]", (wiki / "index.md").read_text(encoding="utf8"))
            self.assertTrue((wiki / "index" / "cat1.md").exists())

            log = (wiki / "log.md").read_text(encoding="utf8")
            self.assertIn("ingest", log)
            self.assertIn("fix", log)


if __name__ == "__main__":
    unittest.main(verbosity=2)
