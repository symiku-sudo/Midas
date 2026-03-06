from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.services.asset_categories import ASSET_CATEGORY_KEYS, ASSET_CATEGORY_SPECS

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一个中文知识整理助手。"
    "请把输入转写整理成结构化 Markdown。"
    "首行必须是一级标题（# 标题），标题要简短具体，建议不超过18个字。"
    "标题禁止使用“这是一份关于……的知识整理”这类模板句。"
    "如需使用该句式，只能放在摘要首句。"
    "正文输出包含：一段摘要、要点列表、可执行建议。"
)

_XHS_PROMPT = (
    "你是一个中文信息提炼助手。"
    "请把输入的小红书笔记整理成 Markdown，输出包含：摘要、关键要点、可执行建议。"
    "严格基于提供的正文，不得根据标题臆测。"
    "若提供了配图，请结合图文共同总结，不可忽略图片信息。"
    "如果信息不足，请明确写出“信息不足”，不要编造细节。"
)

_XHS_VIDEO_PROMPT = (
    "你是一个中文信息提炼助手。"
    "请把输入的小红书视频笔记整理成 Markdown，输出包含：摘要、关键要点、可执行建议。"
    "必须结合视频转写文本与笔记正文（若有），不能遗漏任一来源。"
    "如果视频转写与正文信息冲突，请明确标注冲突点。"
    "如果信息不足，请明确写出“信息不足”，不要编造细节。"
)

_MERGE_PROMPT = (
    "你是中文知识库编辑。"
    "任务是把两条笔记融合为一条高质量 Markdown，而不是简单拼接。"
    "格式硬约束："
    "1) 输出必须沿用“笔记A”的 Markdown 结构和标题层级；"
    "2) 除“## 差异与冲突”外，不得新增或改名其它二级标题；"
    "3) “## 差异与冲突”必须是最后一个二级标题；"
    "4) 首行必须是一级标题（# 标题），标题不超过22字；"
    "5) 严格基于输入内容，不得编造事实。"
)

_COMMENT_INSIGHT_PROMPT = (
    "你是中文舆情分析助手。"
    "请基于评论文本与点赞数做结构化总结。"
    "必须显式体现点赞权重，不可只看评论条数。"
    "输出仅包含三个三级标题："
    "### 公众态度、### 高赞分析、### 样本说明。"
    "其中“高赞分析”需给出要点列表，并引用高赞观点。"
    "严禁编造评论中不存在的事实。"
)

_ASSET_IMAGE_FILL_PROMPT = (
    "你是资产识别助手。"
    "任务：根据用户上传的资产截图，提取并汇总为“万元人民币”。"
    "严禁输出 Markdown 或解释文字，只能输出 JSON。"
    "JSON 顶层必须是对象，并包含 category_amounts 字段。"
    "category_amounts 必须是对象，键只能是规定分类键，值必须是非负数字。"
    "若某分类在图片中未出现，返回 0。"
    "金额单位统一换算为万元人民币（例如 120000 元 -> 12.00）。"
)


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _normalize_image_urls(self, image_urls: list[str] | None) -> list[str]:
        return [
            item.strip()
            for item in (image_urls or [])
            if isinstance(item, str) and item.strip().startswith(("http://", "https://"))
        ]

    def _build_multimodal_user_content(
        self,
        user_text: str,
        image_urls: list[str],
    ) -> list[dict[str, Any]]:
        user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for image_url in image_urls:
            user_content.append(
                {"type": "image_url", "image_url": {"url": image_url}}
            )
        return user_content

    def _chat_completions_url(self) -> str:
        return f"{self._settings.llm.api_base.rstrip('/')}/chat/completions"

    def _require_api_key(self) -> str:
        api_key = self._settings.llm.api_key
        if api_key:
            return api_key
        raise AppError(
            code=ErrorCode.INVALID_INPUT,
            message="LLM 已启用但缺少 api_key 配置。",
            status_code=400,
        )

    def _build_auth_headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _request_chat_completion(
        self,
        payload: dict[str, Any],
        *,
        api_key: str,
        server_error_message: str | None = None,
    ) -> str:
        url = self._chat_completions_url()
        headers = self._build_auth_headers(api_key)
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.llm.timeout_seconds
            ) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("LLM upstream request failed: %s", repr(exc))
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 服务连接失败。",
                status_code=502,
            ) from exc

        if resp.status_code in {401, 403}:
            raise AppError(
                code=ErrorCode.AUTH_EXPIRED,
                message="LLM 鉴权失败，请检查 API Key。",
                status_code=401,
            )
        if resp.status_code == 429:
            raise AppError(
                code=ErrorCode.RATE_LIMITED,
                message="LLM 请求触发限流，请稍后重试。",
                status_code=429,
            )
        if server_error_message and resp.status_code >= 500:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=server_error_message,
                status_code=502,
            )
        if resp.status_code >= 400:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message=f"LLM 请求失败（HTTP {resp.status_code}）。",
                status_code=502,
            )

        raw = resp.json()
        result = self._extract_response_text(raw)
        if not result:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 未返回有效内容。",
                status_code=502,
            )
        return result

    async def summarize(self, transcript: str, video_url: str) -> str:
        if not self._settings.llm.enabled:
            logger.info("LLM disabled, return deterministic local summary")
            preview = transcript[:400].strip()
            return (
                "# B站视频总结（本地降级）\n\n"
                f"- 视频链接：{video_url}\n"
                f"- 转写字数：{len(transcript)}\n\n"
                "## 摘要\n\n"
                "当前为本地降级输出（未启用 LLM）。\n\n"
                "## 转写片段\n\n"
                f"> {preview}\n"
            )

        api_key = self._require_api_key()
        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"视频链接: {video_url}\n\n转写文本:\n{transcript}",
                },
            ],
        }
        logger.info("Request LLM summarize, model=%s", self._settings.llm.model)
        return await self._request_chat_completion(
            payload,
            api_key=api_key,
            server_error_message="LLM 上游服务异常。",
        )

    async def summarize_xiaohongshu_note(
        self,
        *,
        note_id: str,
        title: str,
        content: str,
        source_url: str,
        image_urls: list[str] | None = None,
    ) -> str:
        normalized_image_urls = self._normalize_image_urls(image_urls)
        if not self._settings.llm.enabled:
            preview = content[:300].strip()
            image_section = ""
            if normalized_image_urls:
                image_lines = "\n".join(
                    f"- [配图{i + 1}]({url})"
                    for i, url in enumerate(normalized_image_urls[:6])
                )
                image_section = f"\n## 配图链接\n\n{image_lines}\n"
            return (
                f"# 小红书笔记总结：{title}\n\n"
                f"- 笔记ID：{note_id}\n"
                f"- 来源：{source_url}\n\n"
                "## 摘要\n\n"
                "当前为本地降级输出（未启用 LLM）。\n\n"
                "## 内容片段\n\n"
                f"> {preview}\n"
                f"{image_section}"
            )

        api_key = self._require_api_key()
        user_text = (
            f"笔记ID: {note_id}\n"
            f"标题: {title}\n"
            f"来源: {source_url}\n\n"
            f"正文:\n{content}\n\n"
            f"配图数量: {len(normalized_image_urls)}"
        )
        user_content = self._build_multimodal_user_content(
            user_text=user_text,
            image_urls=normalized_image_urls,
        )

        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _XHS_PROMPT},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }
        return await self._request_chat_completion(payload, api_key=api_key)

    async def summarize_xiaohongshu_video_note(
        self,
        *,
        note_id: str,
        title: str,
        content: str,
        transcript: str,
        source_url: str,
        image_urls: list[str] | None = None,
    ) -> str:
        normalized_image_urls = self._normalize_image_urls(image_urls)
        content_text = content.strip() or "（无正文）"
        transcript_text = transcript.strip()
        if not transcript_text:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="视频转写为空，无法生成视频笔记总结。",
                status_code=502,
            )

        if not self._settings.llm.enabled:
            preview = transcript_text[:400]
            return (
                f"# 小红书视频笔记总结：{title}\n\n"
                f"- 笔记ID：{note_id}\n"
                f"- 来源：{source_url}\n\n"
                "## 正文补充\n\n"
                f"{content_text}\n\n"
                "## 视频转写片段\n\n"
                f"> {preview}\n"
            )

        api_key = self._require_api_key()
        user_text = (
            f"笔记ID: {note_id}\n"
            f"标题: {title}\n"
            f"来源: {source_url}\n\n"
            f"正文:\n{content_text}\n\n"
            f"视频转写:\n{transcript_text}\n\n"
            f"配图数量: {len(normalized_image_urls)}"
        )
        user_content = self._build_multimodal_user_content(
            user_text=user_text,
            image_urls=normalized_image_urls,
        )

        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _XHS_VIDEO_PROMPT},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
        }
        return await self._request_chat_completion(payload, api_key=api_key)

    async def summarize_comment_insights(
        self,
        *,
        platform: str,
        source_title: str,
        source_url: str,
        comments: list[dict[str, Any]],
        max_highlight_items: int,
    ) -> str:
        normalized_comments: list[dict[str, Any]] = []
        for item in comments:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            like_count = item.get("like_count", 0)
            if isinstance(like_count, bool):
                like_count = int(like_count)
            elif isinstance(like_count, (int, float)):
                like_count = int(like_count)
            elif isinstance(like_count, str) and like_count.strip().isdigit():
                like_count = int(like_count.strip())
            else:
                like_count = 0
            normalized_comments.append(
                {
                    "text": text,
                    "like_count": max(int(like_count), 0),
                }
            )

        if not normalized_comments:
            return (
                "### 公众态度\n\n"
                "- 暂未提取到可用评论，无法判断倾向。\n\n"
                "### 高赞分析\n\n"
                "- 暂无可提炼观点。\n\n"
                "### 样本说明\n\n"
                "- 评论样本为空。\n"
            )

        if not self._settings.llm.enabled:
            top_comments = sorted(
                normalized_comments,
                key=lambda item: (int(item["like_count"]), len(str(item["text"]))),
                reverse=True,
            )[: max(int(max_highlight_items), 1)]
            top_lines = "\n".join(
                f"- 👍{int(item['like_count'])}: {str(item['text'])}"
                for item in top_comments
            )
            return (
                "### 公众态度\n\n"
                "- 当前为本地降级输出，观点倾向请结合高赞评论自行判断。\n\n"
                "### 高赞分析\n\n"
                f"{top_lines}\n\n"
                "### 样本说明\n\n"
                f"- 纳入评论：{len(normalized_comments)} 条\n"
                "- 已按点赞数排序提炼。\n"
            )

        api_key = self._require_api_key()
        comment_lines = "\n".join(
            f"{index + 1}. 👍{int(item['like_count'])} | {str(item['text'])}"
            for index, item in enumerate(normalized_comments)
        )
        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _COMMENT_INSIGHT_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"平台: {platform}\n"
                        f"来源标题: {source_title or '（未知）'}\n"
                        f"来源链接: {source_url or '（未知）'}\n"
                        f"高赞洞察条数上限: {max(int(max_highlight_items), 1)}\n\n"
                        f"评论样本（含点赞）:\n{comment_lines}"
                    ),
                },
            ],
        }
        return await self._request_chat_completion(
            payload,
            api_key=api_key,
            server_error_message="LLM 评论洞察生成失败。",
        )

    async def extract_asset_amounts_from_images(
        self,
        *,
        image_data_urls: list[str],
    ) -> dict[str, float]:
        normalized_image_refs = [
            item.strip()
            for item in image_data_urls
            if isinstance(item, str)
            and item.strip()
            and (
                item.strip().startswith("data:image/")
                or item.strip().startswith("http://")
                or item.strip().startswith("https://")
            )
        ]
        if not normalized_image_refs:
            raise AppError(
                code=ErrorCode.INVALID_INPUT,
                message="未检测到可用的图片输入。",
                status_code=400,
            )

        if not self._settings.llm.enabled:
            return {key: 0.0 for key in ASSET_CATEGORY_KEYS}

        api_key = self._require_api_key()
        category_lines = "\n".join(
            f"- {key}: {label}" for key, label in ASSET_CATEGORY_SPECS
        )
        example_json = (
            '{"category_amounts":{"stock":0,"equity_fund":0,"gold":0,'
            '"bond_and_bond_fund":0,"money_market_fund":0,'
            '"bank_fixed_deposit":0,"bank_current_deposit":0,"housing_fund":0}}'
        )
        user_text = (
            "请根据图片识别并汇总资产金额。\n"
            "必须仅返回 JSON，不要输出其它文字。\n"
            "JSON 示例：\n"
            f"{example_json}\n"
            "分类键说明：\n"
            f"{category_lines}\n"
            "金额单位统一为万元人民币，保留两位小数。"
        )
        user_content = self._build_multimodal_user_content(
            user_text=user_text,
            image_urls=normalized_image_refs,
        )
        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": _ASSET_IMAGE_FILL_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
        raw = await self._request_chat_completion(
            payload,
            api_key=api_key,
            server_error_message="LLM 资产图片识别失败。",
        )
        return self._parse_asset_amounts_response(raw)

    async def merge_notes(
        self,
        *,
        source: str,
        first_title: str,
        first_content: str,
        first_ref: str,
        second_title: str,
        second_content: str,
        second_ref: str,
    ) -> str:
        if not self._settings.llm.enabled:
            return self._local_merge_fallback(
                source=source,
                first_title=first_title,
                first_content=first_content,
                first_ref=first_ref,
                second_title=second_title,
                second_content=second_content,
                second_ref=second_ref,
            )

        api_key = self._require_api_key()
        first_trimmed = first_content.strip()[:6000]
        second_trimmed = second_content.strip()[:6000]
        heading_template = self._extract_h2_headings(first_trimmed)
        payload = {
            "model": self._settings.llm.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": _MERGE_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"来源类型: {source}\n\n"
                        f"笔记A二级标题顺序: {heading_template if heading_template else '（无显式二级标题）'}\n\n"
                        "笔记A:\n"
                        f"- 标题: {first_title}\n"
                        f"- 来源: {first_ref}\n"
                        f"- 正文:\n{first_trimmed}\n\n"
                        "笔记B:\n"
                        f"- 标题: {second_title}\n"
                        f"- 来源: {second_ref}\n"
                        f"- 正文:\n{second_trimmed}\n"
                    ),
                },
            ],
        }
        result = await self._request_chat_completion(
            payload,
            api_key=api_key,
            server_error_message="LLM 合并生成失败。",
        )
        fallback_title = (first_title.strip() or second_title.strip() or "合并笔记")[:22]
        normalized = self._normalize_markdown_title(
            markdown=result,
            fallback_title=fallback_title,
        )
        return self._enforce_conflict_section_last(
            markdown=normalized,
            fallback_conflict_lines=self._collect_conflicts(
                first_content,
                second_content,
            ),
        )

    def _local_merge_fallback(
        self,
        *,
        source: str,
        first_title: str,
        first_content: str,
        first_ref: str,
        second_title: str,
        second_content: str,
        second_ref: str,
    ) -> str:
        title = first_title.strip() if len(first_title.strip()) >= len(second_title.strip()) else second_title.strip()
        if not title:
            title = f"{source} 合并笔记"
        base_markdown = (first_content.strip() or second_content.strip() or "").strip()
        if not base_markdown:
            base_markdown = "# 合并笔记\n\n- 信息不足。"
        normalized = self._normalize_markdown_title(
            markdown=base_markdown,
            fallback_title=title[:22],
        )
        fallback_conflicts = self._collect_conflicts(first_content, second_content)
        refs = [item for item in [first_ref.strip(), second_ref.strip()] if item.strip()]
        for index, ref in enumerate(refs, start=1):
            fallback_conflicts.append(f"来源{index}: {ref}")
        return self._enforce_conflict_section_last(
            markdown=normalized,
            fallback_conflict_lines=fallback_conflicts,
        )

    def _collect_unique_lines(self, first: str, second: str, *, max_lines: int) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for raw in (first.splitlines() + second.splitlines()):
            line = raw.strip().lstrip("#").strip()
            if len(line) < 8:
                continue
            if line in seen:
                continue
            seen.add(line)
            output.append(line)
            if len(output) >= max_lines:
                break
        return output

    def _collect_conflicts(self, first: str, second: str) -> list[str]:
        first_set = {
            line.strip().lstrip("#").strip()
            for line in first.splitlines()
            if len(line.strip()) >= 8
        }
        second_set = {
            line.strip().lstrip("#").strip()
            for line in second.splitlines()
            if len(line.strip()) >= 8
        }
        only_first = sorted(first_set - second_set)[:2]
        only_second = sorted(second_set - first_set)[:2]
        conflicts: list[str] = []
        for line in only_first:
            conflicts.append(f"A独有: {line}")
        for line in only_second:
            conflicts.append(f"B独有: {line}")
        return conflicts

    def _extract_h2_headings(self, markdown: str) -> str:
        headings: list[str] = []
        for raw in markdown.splitlines():
            line = raw.strip()
            if not line.startswith("## "):
                continue
            title = line[3:].strip()
            if title:
                headings.append(title)
        return " -> ".join(headings)

    def _normalize_markdown_title(self, *, markdown: str, fallback_title: str) -> str:
        cleaned = markdown.strip()
        if cleaned.startswith("# "):
            return cleaned
        if cleaned:
            return f"# {fallback_title}\n\n{cleaned}".strip()
        return f"# {fallback_title}\n\n- 信息不足。"

    def _enforce_conflict_section_last(
        self,
        *,
        markdown: str,
        fallback_conflict_lines: list[str],
    ) -> str:
        section_pattern = re.compile(
            r"(?ms)^##\s*差异与冲突\s*\n(.*?)(?=^##\s|\Z)"
        )
        existing_blocks = [
            match.group(1).strip()
            for match in section_pattern.finditer(markdown)
            if match.group(1).strip()
        ]
        cleaned = section_pattern.sub("", markdown).strip()
        if existing_blocks:
            conflict_body = existing_blocks[0]
        else:
            normalized_lines = [
                line.strip() for line in fallback_conflict_lines if line.strip()
            ]
            if normalized_lines:
                conflict_body = "\n".join(f"- {line}" for line in normalized_lines)
            else:
                conflict_body = "- 未发现明显冲突。"
        if cleaned:
            return f"{cleaned}\n\n## 差异与冲突\n\n{conflict_body}"
        return f"## 差异与冲突\n\n{conflict_body}"

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="LLM 响应结构异常。",
                status_code=502,
            ) from exc

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    text = item["text"].strip()
                    if text:
                        chunks.append(text)
            return "\n".join(chunks).strip()

        return ""

    def _parse_asset_amounts_response(self, raw_text: str) -> dict[str, float]:
        parsed = self._extract_json_object(raw_text)
        if not isinstance(parsed, dict):
            raise AppError(
                code=ErrorCode.UPSTREAM_ERROR,
                message="资产图片识别结果不是有效 JSON 对象。",
                status_code=502,
            )
        category_amounts_raw = parsed.get("category_amounts")
        if isinstance(category_amounts_raw, dict):
            source = category_amounts_raw
        else:
            source = parsed
        return {
            key: self._coerce_non_negative_amount(source.get(key, 0.0))
            for key in ASSET_CATEGORY_KEYS
        }

    def _extract_json_object(self, raw_text: str) -> dict[str, Any] | None:
        text = raw_text.strip()
        if not text:
            return None
        direct = self._safe_parse_json_object(text)
        if direct is not None:
            return direct

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            parsed = self._safe_parse_json_object(fenced.group(1))
            if parsed is not None:
                return parsed

        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaping = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaping:
                    escaping = False
                elif ch == "\\":
                    escaping = True
                elif ch == "\"":
                    in_string = False
                continue
            if ch == "\"":
                in_string = True
                continue
            if ch == "{":
                depth += 1
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    return self._safe_parse_json_object(candidate)
        return None

    def _safe_parse_json_object(self, text: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
        return None

    def _coerce_non_negative_amount(self, raw: object) -> float:
        value = 0.0
        if isinstance(raw, bool):
            value = float(int(raw))
        elif isinstance(raw, (int, float)):
            value = float(raw)
        elif isinstance(raw, str):
            normalized = raw.strip()
            for token in ("万元人民币", "万元", "万", "人民币", "元"):
                normalized = normalized.replace(token, "")
            normalized = normalized.replace(",", "").strip()
            if normalized:
                try:
                    value = float(normalized)
                except ValueError:
                    value = 0.0
        if not value or not value.isfinite() or value < 0:
            return 0.0
        return round(value, 2)
