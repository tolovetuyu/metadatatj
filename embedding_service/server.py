"""本地向量模型服务 - FastAPI 实现。

兼容 OpenAI Embedding API 格式，支持中文向量模型。
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Union
import logging

# 使用 FastEmbed 作为向量模型库
from fastembed import TextEmbedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Local Embedding Service", version="1.0.0")

# 默认使用中文向量模型
# 可选模型：
# - BAAI/bge-small-zh-v1.5 (512维，轻量)
# - BAAI/bge-base-zh-v1.5 (768维，推荐)
# - BAAI/bge-large-zh-v1.5 (1024维，高性能)
DEFAULT_MODEL = "BAAI/bge-base-zh-v1.5"

# 全局模型实例
embedding_model = None


def get_embedding_model(model_name: str = DEFAULT_MODEL):
    """获取或初始化向量模型。"""
    global embedding_model
    if embedding_model is None:
        logger.info(f"Loading embedding model: {model_name}")
        embedding_model = TextEmbedding(model_name=model_name)
        logger.info(f"Model loaded successfully")
    return embedding_model


class EmbeddingRequest(BaseModel):
    """兼容 OpenAI Embedding API 请求格式。"""
    model: str = DEFAULT_MODEL
    input: Union[str, List[str]]
    encoding_format: str = "float"


class EmbeddingResponse(BaseModel):
    """兼容 OpenAI Embedding API 响应格式。"""
    object: str = "list"
    data: List[dict]
    model: str
    usage: dict


@app.on_event("startup")
async def startup_event():
    """启动时预加载模型。"""
    logger.info("Preloading embedding model...")
    get_embedding_model()
    logger.info("Model preloaded, service ready")


@app.get("/")
async def root():
    """健康检查。"""
    return {"status": "ok", "service": "Local Embedding Service"}


@app.get("/v1/models")
async def list_models():
    """列出可用模型。"""
    return {
        "object": "list",
        "data": [
            {"id": "BAAI/bge-small-zh-v1.5", "object": "model", "dimensions": 512},
            {"id": "BAAI/bge-base-zh-v1.5", "object": "model", "dimensions": 768},
            {"id": "BAAI/bge-large-zh-v1.5", "object": "model", "dimensions": 1024},
        ]
    }


@app.post("/v1/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """创建向量嵌入。"""
    try:
        model = get_embedding_model(request.model)
        
        # 处理输入：可以是单个字符串或字符串列表
        texts = request.input if isinstance(request.input, list) else [request.input]
        
        logger.info(f"Embedding {len(texts)} texts with model {request.model}")
        
        # 计算向量
        embeddings = list(model.embed(texts))
        
        # 构建响应（兼容 OpenAI 格式）
        data = []
        for i, embedding in enumerate(embeddings):
            data.append({
                "object": "embedding",
                "index": i,
                "embedding": embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
            })
        
        return EmbeddingResponse(
            object="list",
            data=data,
            model=request.model,
            usage={
                "prompt_tokens": sum(len(t) for t in texts),
                "total_tokens": sum(len(t) for t in texts)
            }
        )
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)