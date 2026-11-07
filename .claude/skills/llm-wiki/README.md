# llm-wiki

把归档 Markdown 编译成交叉链接知识百科的 CLI + Claude Code skill（**自包含版**）。

基于 `BookerMarkdownTool` 的 `wiki` 子命令封装，但所有项目内依赖都已作为源码副本
vendored 到 `src/wiki_tool/` 下：**运行时不 import 任何 BookerMarkdownTool 代码，
也不依赖当前工作目录**，可放在任意位置直接运行。

- skill 定义见 `SKILL.md`。
- 第三方依赖：`openai`、`pydantic`、`pyyaml`、`json_repair`。

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```bash
python d:/src/skills/llm-wiki/src/wiki.py --help
python d:/src/skills/llm-wiki/src/wiki.py D:/wiki -i D:/inbox
python d:/src/skills/llm-wiki/src/wiki.py D:/wiki -l 3 -f
```

API 配置通过参数或环境变量提供：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、
`OPENAI_CHAT_MODEL`。

## 目录结构

```text
llm-wiki/
├── SKILL.md
├── README.md
├── requirements.txt
├── src/
│   ├── wiki.py              # 独立 CLI 入口
│   └── wiki_tool/
│       ├── md2wiki.py       # 编排器（分类可配置、CRLF frontmatter 兼容）
│       ├── md2wiki_agent.py # LLM 调用封装
│       ├── md2wiki_models.py
│       ├── md2wiki_pmt.py
│       ├── llm.py           # 精简版 OpenAI 对话客户端
│       └── util.py          # 精简版工具函数
└── tests/
    └── test_smoke.py        # 离线冒烟测试
```

## 副本来源

自 `BookerMarkdownTool` 版本 `2026.3.25.0` 派生：

- 原样复制：`md2wiki_models.py`、`md2wiki_pmt.py`。
- 改写导入：`md2wiki.py`、`md2wiki_agent.py`。
- 精简复制：`openai.py` → `llm.py`（移除视觉/TTI/工具调用/`ctx_compact`
  相关代码）；`util.py` → `util.py`（仅保留 4 个 wiki 所需函数）。

相对原命令的行为差异仅有两处：

1. 新增 `--categories`（及环境变量 `WIKI_CATEGORIES`）覆盖分类列表，默认仍是原有
   5 个分类。
2. frontmatter 正则支持 CRLF 换行，避免 Windows 源文件被误判为无 frontmatter。

## 测试

```bash
python tests/test_smoke.py
```
