"""精简版 OpenAI 对话客户端（从 BookerMarkdownTool/openai.py 派生）。

只保留 wiki 工作流用到的能力：对话 / 流式累积 / 重试 / 复读检测。
视觉、文生图、工具调用循环等与本技能无关的代码及依赖已移除。
"""

import json
import logging
import re
import traceback

import openai

from wiki_tool.util import json_dump_model


logging.getLogger("openai._base_client").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

NO_THINK_EXTRA_BODY = {
    "reasoning_effort": "none",
    "chat_template_kwargs": {
        "enable_thinking": False,
        "thinking_mode": "off",
        "reasoning_effort": "none",
        "reasoning_strength": "none"
    }
}


def get_msgs_text(msgs):
    for m in msgs[::-1]:
        cont = m.get('content')
        if isinstance(cont, str):
            return m['content']
        elif isinstance(cont, list):
            for it in m['content']:
                tp = it.get('type')
                if tp == 'text':
                    return it['text']
    return ''


def repl_ins_token(msgs):
    repl_ins_token_re = lambda s: re.sub(r'<\|([\w\-\.]+)\|>', r'</\1/>', s)
    for m in msgs:
        cont = m.get('content')
        if isinstance(cont, str):
            m['content'] = ensure_utf8(
                repl_ins_token_re(m['content']))
        elif isinstance(cont, list):
            for it in m['content']:
                tp = it.get('type')
                if tp == 'text':
                    it['text'] = ensure_utf8(
                        repl_ins_token_re(it['text']))
    return msgs


def ensure_utf8(text: str) -> str:
    return text.encode('utf8', 'ignore').decode('utf8', 'ignore')


class OpenAIClient:
    """封装 OpenAI API 对话调用，配置保存在实例上。"""

    def __init__(
        self,
        api_key=None,
        base_url=None,
        user_agent='claude-cli/2.1.41 (external, cli)',
        stream=False,
        timeout=None,
        rpre='',
        no_think=False,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.user_agent = user_agent
        self.stream = stream
        self.timeout = timeout
        self.rpre = rpre
        self.no_think = no_think

    @classmethod
    def from_args(cls, args):
        """从命令行参数对象构造 OpenAIClient。"""
        return cls(
            api_key=getattr(args, 'key', None),
            base_url=getattr(args, 'host', None),
            user_agent=getattr(args, 'user_agent', 'claude-cli/2.1.41 (external, cli)'),
            stream=not getattr(args, 'no_stream', False),
            timeout=openai.Timeout(
                read=getattr(args, 'read_timeout', 120),
                connect=getattr(args, 'conn_timeout', 60),
                write=None,
                pool=None,
            ),
            rpre=getattr(args, 'repetition_regex', ''),
            no_think=getattr(args, 'no_think', False),
        )

    def _build_client(self) -> openai.OpenAI:
        return openai.OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            default_headers={'User-Agent': self.user_agent},
            timeout=self.timeout,
        )

    # ── 对话 ──────────────────────────────────────────

    def call_llm(
        self, msgs, model_name, *,
        temp=None,
        top_p=None,
        frequency_penalty=None,
        presence_penalty=None,
        max_tokens=None,
        extra_body=None,
    ):
        if isinstance(msgs, str):
            msgs = [{'role': 'user', 'content': msgs}]
        # 改变指令符号的形式，避免模型出错
        msgs = repl_ins_token(msgs)
        extra_body = extra_body or {}
        if isinstance(extra_body, str):
            extra_body = json.loads(extra_body)
        if self.no_think:
            extra_body.update(NO_THINK_EXTRA_BODY)
        logger.debug(f'ques: %s', json_dump_model(get_msgs_text(msgs)))
        sdk = self._build_client()
        res = sdk.chat.completions.create(
            messages=msgs,
            model=model_name,
            temperature=temp,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            max_tokens=max_tokens,
            extra_body=extra_body,
            stream=self.stream,
        )
        if self.stream:
            ans, rc = self.collect_stream_content(res)
        else:
            ans = res.choices[0].message.content.strip()
            rc = getattr(res.choices[0].message, 'reasoning_content', "").strip()
            self.check_model_repetition(ans)
        if not ans:
            raise ValueError(f'回复为空：{res}')

        # 还原指令格式
        ans = re.sub(r'</([\w\-\.]+)/>', r'<|\1|>', ans)
        ans = re.sub(r' thinking[\s\S]+? response', '', ans)
        logger.debug(f'ans: %s', json_dump_model(ans))
        return ans

    def call_llm_retry(
        self, msgs, model_name, *,
        retry=10,
        temp=None,
        top_p=None,
        frequency_penalty=None,
        presence_penalty=None,
        max_tokens=None,
        extra_body=None,
        parse_output=None,
    ):
        for i in range(retry):
            try:
                res = self.call_llm(
                    msgs, model_name,
                    temp=temp,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    max_tokens=max_tokens,
                    extra_body=extra_body,
                )
                return (
                    parse_output(res)
                    if parse_output else res
                )
            except KeyboardInterrupt:
                raise
            except Exception as ex:
                logger.debug(f'OpenAI retry {i+1}')
                logger.debug(traceback.format_exc())
                if i == retry - 1: raise ex

    def ask_chatgpt_retry(
        self, ques, model_name, args,
        parse_output=None,
    ):
        return self.call_llm_retry(
            ques, model_name,
            retry=args.retry,
            temp=args.temp,
            top_p=args.top_p,
            frequency_penalty=args.frequency_penalty,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_tokens,
            extra_body=args.extra_body,
            parse_output=parse_output,
        )

    # ── 流式/重复检测 ─────────────────────────────────

    def collect_stream_content(self, resp):
        content = []
        rc = []
        for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            delta_content = delta.content
            delta_rc = getattr(delta, 'reasoning_content', "")
            if delta_content:
                content.append(delta_content)
                self.check_model_repetition(''.join(content))
                logger.debug(f'stream: %s', json_dump_model(delta_content))
            if delta_rc:
                rc.append(delta_rc)
                self.check_model_repetition(''.join(rc))
                logger.debug(f'reasoning stream: %s', json_dump_model(delta_rc))
        return ''.join(content), ''.join(rc)

    def check_model_repetition(self, text):
        if self.rpre and re.search(self.rpre, text):
            raise ValueError('检测到模型复读')
