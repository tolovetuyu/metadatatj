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
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("LLM 返回非 JSON: %s", content[:500])
            raise RuntimeError("LLM 返回格式错误") from exc


class EmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not settings.embedding_api_key:
            raise RuntimeError("EMBEDDING_API_KEY 未配置")

        # 处理 API 路径：如果 base_url 已经包含 /embeddings，则不再拼接
        base_url = settings.embedding_api_base.rstrip("/")
        if base_url.endswith("/embeddings"):
            url = base_url
        else:
            url = f"{base_url}/embeddings"

        headers = {
            "Authorization": f"Bearer {settings.embedding_api_key}",
            "Content-Type": "application/json",
        }
        all_vectors: list[list[float]] = []
        batch_size = settings.embedding_batch_size

        with httpx.Client(timeout=settings.embedding_timeout) as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                # 阿里云百炼 Embedding API 格式
                # input 可以是单个字符串或字符串数组
                # 为确保兼容性，单个文本时传字符串，多个文本时传数组
                if len(batch) == 1:
                    payload = {"model": settings.embedding_model, "input": batch[0]}
                else:
                    payload = {"model": settings.embedding_model, "input": batch}
                logger.info(f"Embedding request: url={url}, model={settings.embedding_model}, batch_size={len(batch)}, input_type={type(payload['input']).__name__}")
                logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)[:200]}")
                try:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    result = resp.json()
                    data = result["data"]
                    data.sort(key=lambda x: x["index"])
                    all_vectors.extend(item["embedding"] for item in data)
                except httpx.HTTPStatusError as e:
                    logger.error(f"Embedding API error: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                    raise
        return all_vectors

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
