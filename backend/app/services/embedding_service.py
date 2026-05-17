"""
Embedding 服务 — Gemini gemini-embedding-001 截到 768 维

调用 Google GenAI SDK 的 embed_content 接口（v1beta endpoint）。
模型默认输出 3072 维；通过 EmbedContentConfig.output_dimensionality=768
利用 MRL 截断到 768 维，与 DB 的 Vector(768) 对齐。

⚠️ Gemini 免费档对 embed_content 有 100 RPM 限制。
   付费档（Pay-As-You-Go）可达 3000 RPM，强烈建议在生产环境启用。

批量调用、失败重试、并发限速。与 [llm.py](app/services/llm.py) 共享 AIConfig 配置表，
若没有 provider=gemini 的 AIConfig，回退到 SystemConfig 'llm_api_key'。
"""
import asyncio
import logging
from typing import List, Optional

from sqlmodel import Session, select

from app.models.ai_config import AIConfig
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai_types = None  # type: ignore
    logger.warning("google-genai not installed, embedding service disabled")


# gemini-embedding-001 是 AI Studio v1beta 端点上当前可用的 embedding 模型。
# 默认 3072 维；通过 output_dimensionality 截断到 768（MRL 训练支持），
# 与 DB schema Vector(768) 对齐。
DEFAULT_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
MAX_CONCURRENCY = 5
# gemini-embedding-001 限制：单次 batch 最多 100 条；MVP 用 64 留余量
MAX_BATCH_SIZE = 64
MAX_INPUT_CHARS = 8000  # 单条文本最长（避免 token 超限）


class EmbeddingService:
    def __init__(self, db_session: Session, model: str = DEFAULT_MODEL):
        self.session = db_session
        self.model = model
        self.client = None
        self.api_key: Optional[str] = None
        self._sem = asyncio.Semaphore(MAX_CONCURRENCY)
        self._init_client()

    def _init_client(self) -> None:
        if not GEMINI_AVAILABLE:
            return

        api_key = self._load_gemini_api_key()
        if not api_key:
            logger.warning("Gemini API key not configured; embedding service inactive")
            return

        try:
            self.api_key = api_key
            self.client = genai.Client(api_key=api_key)
            logger.info(f"Embedding client initialized with model: {self.model}")
        except Exception as e:
            logger.error(f"Embedding client init failed: {e}")
            self.client = None

    def _load_gemini_api_key(self) -> Optional[str]:
        try:
            cfg = self.session.exec(
                select(AIConfig)
                .where(AIConfig.provider == "gemini")
                .where(AIConfig.is_active == True)  # noqa: E712
                .order_by(AIConfig.is_default.desc())
            ).first()
            if cfg and cfg.api_key:
                return cfg.api_key
        except Exception as e:
            logger.debug(f"AIConfig lookup failed: {e}")

        try:
            row = self.session.exec(
                select(SystemConfig).where(SystemConfig.key == "llm_api_key")
            ).first()
            if row and row.value:
                provider_row = self.session.exec(
                    select(SystemConfig).where(SystemConfig.key == "llm_provider")
                ).first()
                if provider_row and provider_row.value == "gemini":
                    return row.value
        except Exception:
            pass
        return None

    def is_configured(self) -> bool:
        return self.client is not None

    @staticmethod
    def _clip(text: str) -> str:
        if not text:
            return ""
        return text[:MAX_INPUT_CHARS]

    async def embed(self, text: str) -> Optional[List[float]]:
        if not self.is_configured() or not text or not text.strip():
            return None
        results = await self.embed_batch([text])
        return results[0] if results else None

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        批量 embed。返回与输入等长的列表，失败项为 None。
        """
        if not self.is_configured():
            return [None] * len(texts)

        cleaned = [self._clip(t or "") for t in texts]
        out: List[Optional[List[float]]] = [None] * len(texts)

        tasks = []
        for start in range(0, len(cleaned), MAX_BATCH_SIZE):
            chunk = cleaned[start:start + MAX_BATCH_SIZE]
            tasks.append(self._embed_chunk(chunk, start, out))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=False)
        return out

    async def _embed_chunk(
        self,
        chunk: List[str],
        start_index: int,
        out: List[Optional[List[float]]],
    ) -> None:
        async with self._sem:
            vectors = await self._call_with_retry(chunk)
        if not vectors:
            return
        for i, vec in enumerate(vectors):
            out[start_index + i] = vec

    async def _call_with_retry(self, chunk: List[str]) -> Optional[List[Optional[List[float]]]]:
        # 空字符串占位输入直接返回 None，不发请求
        non_empty_idx = [i for i, t in enumerate(chunk) if t]
        if not non_empty_idx:
            return [None] * len(chunk)

        send_payload = [chunk[i] for i in non_empty_idx]

        # 通过 EmbedContentConfig 把 3072 维输出截断到 768
        embed_config = genai_types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIM,
        ) if genai_types else None

        for attempt in range(3):
            try:
                response = await asyncio.to_thread(
                    self.client.models.embed_content,
                    model=self.model,
                    contents=send_payload,
                    config=embed_config,
                )
                vectors: List[Optional[List[float]]] = [None] * len(chunk)
                embeddings = getattr(response, "embeddings", None) or []
                for slot, emb in zip(non_empty_idx, embeddings):
                    values = getattr(emb, "values", None)
                    if values:
                        vectors[slot] = list(values)
                return vectors
            except Exception as e:
                err_str = str(e)
                transient = (
                    "503" in err_str
                    or "UNAVAILABLE" in err_str
                    or "429" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "DEADLINE_EXCEEDED" in err_str
                )
                if attempt < 2 and transient:
                    backoff = 2 ** attempt * 2
                    logger.warning(
                        f"Embedding transient error (attempt {attempt + 1}), "
                        f"retrying in {backoff}s: {e}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Embedding call failed (chunk size {len(send_payload)}): {e}")
                return None
        return None
