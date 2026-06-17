# -*- coding: utf-8 -*-
"""OpenAI 兼容 HTTP 客户端。"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY 未配置")

        url = f"{settings.llm_api_base}/chat/completions"
        payload = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=settings.llm_timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        try:
            # 尝试直接解析 JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取 Markdown 中的 JSON
            json_str = self._extract_json_from_markdown(content)
            if json_str:
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as exc:
                    logger.error("LLM 返回非 JSON: %s", content[:500])
                    raise RuntimeError("LLM 返回格式错误") from exc
            else:
                logger.error("LLM 返回非 JSON: %s", content[:500])
                raise RuntimeError("LLM 返回格式错误")

    def _extract_json_from_markdown(self, content: str) -> str | None:
        """从 Markdown 格式中提取 JSON 内容。"""
        import re
        
        # 先移除思考过程标签（如  ... ）
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        content = re.sub(r'思考过程：.*?(?=```|\{)', '', content, flags=re.DOTALL)
        
        # 尝试匹配 ```json ... ``` 格式
        pattern = r'```json\s*(.*?)\s*```'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # 尝试匹配 ``` ... ``` 格式（没有 json 标记）
        pattern = r'```\s*(.*?)\s*```'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            result = match.group(1).strip()
            # 检查是否是 JSON（以 { 开头）
            if result.startswith('{') or result.startswith('['):
                return result
        
        # 尝试匹配 { ... } 格式（直接 JSON）
        pattern = r'\{[^{}]*\}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(0).strip()
        
        # 尝试匹配嵌套的 { ... } 格式
        pattern = r'\{.*\}'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(0).strip()
        
        return None

    def chat_text(self, system: str, user: str) -> str:
        """Call LLM and return plain text response (not JSON)."""
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY 未配置")

        url = f"{settings.llm_api_base}/chat/completions"
        payload = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=settings.llm_timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        
        # 移除思考过程标签（如 <think>...</think>）
        content = self._remove_think_tags(content)
        
        # 移除多余的空行（保留单个空行）
        content = self._remove_extra_blank_lines(content)
        
        return content

    def _remove_think_tags(self, content: str) -> str:
        """移除思考过程标签。"""
        import re
        
        # 移除 <think>...</think> 标签及其内容
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # 移除 Markdown 格式的思考过程标签
        content = re.sub(r'```think.*?```', '', content, flags=re.DOTALL)
        
        # 移除 "思考过程："开头的段落
        content = re.sub(r'思考过程：.*?(?=##|\n\n|$)', '', content, flags=re.DOTALL)
        
        return content.strip()

    def _remove_extra_blank_lines(self, content: str) -> str:
        """移除多余的空行（保留单个空行）。"""
        import re
        
        # 将连续的多个空行替换为单个空行
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 移除行首和行尾的空行
        content = content.strip()
        
        return content


class EmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not settings.embedding_api_base:
            raise RuntimeError("EMBEDDING_API_BASE 未配置")

        # 构建 URL：确保 base 不以 /embeddings 结尾则拼接
        base = settings.embedding_api_base.rstrip("/")
        if not base.endswith("/embeddings"):
            url = f"{base}/embeddings"
        else:
            url = base

        headers = {
            "Content-Type": "application/json",
        }
        # 如果有 API Key 则添加（Ollama 不需要，阿里云需要）
        if settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {settings.embedding_api_key}"

        all_vectors: list[list[float]] = []

        # 根据 URL 判断是否是 Ollama（Ollama 不支持批量）
        is_ollama = "11434" in url or "ollama" in url.lower() or "/api/embeddings" in url

        with httpx.Client(timeout=settings.embedding_timeout) as client:
            for i in range(0, len(texts), settings.embedding_batch_size):
                batch = texts[i : i + settings.embedding_batch_size]

                if is_ollama:
                    # Ollama 格式：不支持批量，需要循环
                    logger.info(f"Embedding request (Ollama format): url={url}, model={settings.embedding_model}, texts={len(batch)}")
                    for text in batch:
                        payload = {
                            "model": settings.embedding_model,
                            "prompt": text
                        }
                        try:
                            resp = client.post(url, headers=headers, json=payload)
                            resp.raise_for_status()
                            result = resp.json()
                            # 检查响应格式
                            if "embedding" not in result:
                                logger.error(f"Unexpected response format: {json.dumps(result, ensure_ascii=False)[:500]}")
                                raise RuntimeError(f"Embedding API 返回格式错误，缺少 'embedding' 字段")
                            all_vectors.append(result["embedding"])
                        except httpx.HTTPStatusError as e:
                            logger.error(f"Embedding API error: {e.response.status_code}")
                            logger.error(f"Response body: {e.response.text}")
                            raise
                else:
                    # OpenAI/阿里云格式：支持批量
                    payload = {
                        "model": settings.embedding_model,
                        "input": batch if len(batch) > 1 else batch[0]
                    }
                    logger.info(f"Embedding request (OpenAI format): url={url}, model={settings.embedding_model}, batch_size={len(batch)}")
                    try:
                        resp = client.post(url, headers=headers, json=payload)
                        resp.raise_for_status()
                        result = resp.json()
                        
                        # 根据响应格式自动判断
                        if "data" in result:
                            # OpenAI/阿里云格式
                            data = result["data"]
                            data.sort(key=lambda x: x["index"])
                            all_vectors.extend(item["embedding"] for item in data)
                        elif "embedding" in result:
                            # Ollama 格式响应，但请求格式不对，需要重新用 Ollama 格式请求
                            logger.warning(f"检测到 Ollama 格式响应，但 URL 判断为非 Ollama，请检查配置")
                            for text in batch:
                                ollama_payload = {
                                    "model": settings.embedding_model,
                                    "prompt": text
                                }
                                resp = client.post(url, headers=headers, json=ollama_payload)
                                resp.raise_for_status()
                                ollama_result = resp.json()
                                if "embedding" not in ollama_result:
                                    logger.error(f"Unexpected response format: {json.dumps(ollama_result, ensure_ascii=False)[:500]}")
                                    raise RuntimeError(f"Embedding API 返回格式错误，缺少 'embedding' 字段")
                                all_vectors.append(ollama_result["embedding"])
                        else:
                            logger.error(f"Unexpected response format: {json.dumps(result, ensure_ascii=False)[:500]}")
                            raise RuntimeError(f"Embedding API 返回格式错误，缺少 'data' 或 'embedding' 字段")
                    except httpx.HTTPStatusError as e:
                        logger.error(f"Embedding API error: {e.response.status_code}")
                        logger.error(f"Response body: {e.response.text}")
                        raise

        return all_vectors

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
