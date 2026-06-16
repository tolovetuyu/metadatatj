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

        with httpx.Client(timeout=settings.embedding_timeout) as client:
            for i in range(0, len(texts), settings.embedding_batch_size):
                batch = texts[i : i + settings.embedding_batch_size]

                # 根据是否有 API Key 判断使用哪种格式
                if settings.embedding_api_key:
                    # 阿里云/OpenAI 格式：支持批量
                    payload = {
                        "model": settings.embedding_model,
                        "input": batch if len(batch) > 1 else batch[0]
                    }
                    logger.info(f"Embedding request (OpenAI format): url={url}, model={settings.embedding_model}, batch_size={len(batch)}")
                    try:
                        resp = client.post(url, headers=headers, json=payload)
                        resp.raise_for_status()
                        data = resp.json()["data"]
                        data.sort(key=lambda x: x["index"])
                        all_vectors.extend(item["embedding"] for item in data)
                    except httpx.HTTPStatusError as e:
                        logger.error(f"Embedding API error: {e.response.status_code}")
                        logger.error(f"Response body: {e.response.text}")
                        raise
                else:
                    # Ollama 格式：不支持批量，需要循环
                    logger.info(f"Embedding request (Ollama format): url={url}, model={settings.embedding_model}, batch_size={len(batch)}")
                    for text in batch:
                        payload = {
                            "model": settings.embedding_model,
                            "prompt": text
                        }
                        try:
                            resp = client.post(url, headers=headers, json=payload)
                            resp.raise_for_status()
                            all_vectors.append(resp.json()["embedding"])
                        except httpx.HTTPStatusError as e:
                            logger.error(f"Embedding API error: {e.response.status_code}")
                            logger.error(f"Response body: {e.response.text}")
                            raise

        return all_vectors

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
