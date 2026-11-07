"""llm-wiki 自带的工具函数（从 BookerMarkdownTool/util.py 精简）。

只保留 wiki 工作流实际用到的纯函数，避免引入 requests/pyquery/imgyaso 等
与知识库编译无关的重型依赖。
"""

import json
import re

from pydantic import BaseModel


def render_prompt(prompt: str, **kw):
    """用 kw 替换 prompt 中的 {name} 占位符；未知占位符保持原样。"""
    return re.sub(r"{(\w+)}", lambda g: kw.get(g.group(1), g.group(0)), prompt)


def ext_code_block(s):
    """从包含 ``` 围栏的文本中提取围栏内的内容。"""
    return re.search(r'```\w*([\s\S]+)```', s).group(1)


def ext_cont_block(s):
    """从 [content]...[/content] 中提取内容。"""
    return re.search(r'\[content\]([\s\S]+)\[/content\]', s).group(1)


def json_dump_model(obj) -> str:
    """将对象（含 pydantic 模型/列表）序列化为 JSON 字符串。"""
    if isinstance(obj, BaseModel):
        obj = obj.model_dump()
    elif isinstance(obj, list):
        obj = [
            it.model_dump() if isinstance(it, BaseModel) else it
            for it in obj
        ]
    return json.dumps(obj, ensure_ascii=False)
