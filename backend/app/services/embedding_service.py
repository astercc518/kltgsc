"""
Embedding 服务 — gemini-embedding-001 截到 768 维

调用 Google GenAI SDK 的 embed_content 接口。优先走 Vertex AI（与 LLM 共用 GCP
项目计费、无 AI Studio 免费档 RPM 限制），找不到 vertex 配置时回退到 AI Studio
Gemini API key。

模型默认输出 3072 维；通过 EmbedContentConfig.output_dimensionality=768
利用 MRL 截断到 768 维，与 DB 的 Vector(768) 对齐。

配置加载优先级：
  1. AIConfig.provider="vertex"（推荐，付费档 GCP 配额）
  2. AIConfig.provider="gemini"（AI Studio key，免费档 100 RPM）
  3. SystemConfig llm_api_key（legacy 兼容，仅当 llm_provider=gemini）

embed_text() — 统一 768 维 embedding 入口（薄包装 industry_kb_service._embed_text）。
ICP 画像 / case_studies / 群消息 Layer 2 匹配都通过本函数调用。
参考 spec §3.2 (Layer 2 ICP embedding)
"""
import asyncio
import json
import logging
import os
import tempfile
from typing import List, Optional

# NOTE: _embed_text_raw is imported lazily inside embed_text() to break the
# circular dependency: industry_kb_service imports EmbeddingService from here.

from sqlmodel import Session, select

from app.models.ai_config import AIConfig
from app.models.system_config import SystemConfig
from app.services.pricing import estimate_embedding_tokens
from app.services.usage_tracker import record_usage

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
        self.provider: Optional[str] = None
        self.api_key: Optional[str] = None
        self._sem = asyncio.Semaphore(MAX_CONCURRENCY)
        self._init_client()

    def _init_client(self) -> None:
        if not GEMINI_AVAILABLE:
            return

        cfg = self._load_ai_config()
        if cfg is None:
            logger.warning(
                "No Vertex/Gemini AIConfig found and no legacy SystemConfig; "
                "embedding service inactive"
            )
            return

        provider, payload = cfg
        try:
            if provider == "vertex":
                self.client = self._build_vertex_client(payload)
            else:
                self.api_key = payload
                self.client = genai.Client(api_key=payload)
            self.provider = provider
            logger.info(
                f"Embedding client initialized: provider={provider} model={self.model}"
            )
        except Exception as e:
            logger.error(f"Embedding client init failed (provider={provider}): {e}")
            self.client = None

    def _build_vertex_client(self, cfg: AIConfig):
        """
        Vertex AI client. base_url 期望是 JSON {project_id, location}；
        api_key 是 Service Account JSON 字符串。回退到 SystemConfig
        gcp_project_id / gcp_service_account_json / gcp_location（与 llm.py 一致）。
        """
        project_id = None
        location = "us-central1"
        sa_json_str = None

        if cfg.base_url:
            try:
                parsed = json.loads(cfg.base_url)
                project_id = parsed.get("project_id")
                location = parsed.get("location", location)
            except (json.JSONDecodeError, TypeError):
                pass

        if cfg.api_key:
            stripped = cfg.api_key.strip()
            if stripped.startswith("{"):
                sa_json_str = stripped

        if not project_id:
            project_id = self._get_system_config("gcp_project_id")
        if not sa_json_str:
            sa_json_str = self._get_system_config("gcp_service_account_json")
        if location == "us-central1":
            sys_loc = self._get_system_config("gcp_location")
            if sys_loc:
                location = sys_loc

        if not project_id:
            raise RuntimeError("Vertex embedding: gcp_project_id not configured")

        if sa_json_str:
            sa_data = json.loads(sa_json_str)
            tf = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, prefix="tgsc_emb_sa_"
            )
            json.dump(sa_data, tf)
            tf.close()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tf.name
            logger.info(f"Vertex embedding using service account: {tf.name}")
        else:
            logger.info("Vertex embedding using Application Default Credentials (ADC)")

        return genai.Client(vertexai=True, project=project_id, location=location)

    def _load_ai_config(self):
        """
        返回 (provider, payload):
          - ("vertex", AIConfig)        — Vertex 走 SA / ADC，payload 是配置对象
          - ("gemini", api_key_string)  — AI Studio 走 API key
          - None                         — 没有可用配置
        """
        try:
            vertex_cfg = self.session.exec(
                select(AIConfig)
                .where(AIConfig.provider == "vertex")
                .where(AIConfig.is_active == True)  # noqa: E712
                .order_by(AIConfig.is_default.desc())
            ).first()
            if vertex_cfg:
                return ("vertex", vertex_cfg)
        except Exception as e:
            logger.debug(f"Vertex AIConfig lookup failed: {e}")

        try:
            gemini_cfg = self.session.exec(
                select(AIConfig)
                .where(AIConfig.provider == "gemini")
                .where(AIConfig.is_active == True)  # noqa: E712
                .order_by(AIConfig.is_default.desc())
            ).first()
            if gemini_cfg and gemini_cfg.api_key:
                return ("gemini", gemini_cfg.api_key)
        except Exception as e:
            logger.debug(f"Gemini AIConfig lookup failed: {e}")

        try:
            row = self.session.exec(
                select(SystemConfig).where(SystemConfig.key == "llm_api_key")
            ).first()
            if row and row.value:
                provider_row = self.session.exec(
                    select(SystemConfig).where(SystemConfig.key == "llm_provider")
                ).first()
                if provider_row and provider_row.value == "gemini":
                    return ("gemini", row.value)
        except Exception:
            pass
        return None

    def _get_system_config(self, key: str) -> Optional[str]:
        try:
            row = self.session.exec(
                select(SystemConfig).where(SystemConfig.key == key)
            ).first()
            return row.value if row else None
        except Exception:
            return None

    def is_configured(self) -> bool:
        return self.client is not None

    @staticmethod
    def _clip(text: str) -> str:
        if not text:
            return ""
        return text[:MAX_INPUT_CHARS]

    async def embed(
        self,
        text: str,
        source: str = "embedding_runtime",
        account_id: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> Optional[List[float]]:
        if not self.is_configured() or not text or not text.strip():
            return None
        results = await self.embed_batch(
            [text], source=source, account_id=account_id, chat_id=chat_id,
        )
        return results[0] if results else None

    async def embed_batch(
        self,
        texts: List[str],
        source: str = "embedding_runtime",
        account_id: Optional[int] = None,
        chat_id: Optional[str] = None,
    ) -> List[Optional[List[float]]]:
        """
        批量 embed。返回与输入等长的列表，失败项为 None。
        每个成功的非空文本上报一次 usage（按 char→token 估算）。
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

        # 上报成功项的 usage（聚合成一条以减少写入次数）
        total_tokens = 0
        success_count = 0
        for i, vec in enumerate(out):
            if vec and cleaned[i]:
                total_tokens += estimate_embedding_tokens(cleaned[i])
                success_count += 1
        if success_count > 0:
            record_usage(
                provider=self.provider or "vertex",
                model=self.model,
                source=source,
                input_tokens=total_tokens,
                output_tokens=0,
                account_id=account_id,
                chat_id=chat_id,
            )
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


# ---------------------------------------------------------------------------
# embed_text — 统一薄包装入口（供 ICP / case_study / Layer 2 使用）
# ---------------------------------------------------------------------------

def _embed_text_raw(session, text: str, timeout: float = 15.0) -> Optional[List[float]]:
    """
    Thin shim that delegates to industry_kb_service._embed_text.
    Defined here so tests can patch 'app.services.embedding_service._embed_text_raw'
    without triggering the circular import.  The real import is deferred to first call.
    """
    # Lazy import breaks the circular dependency:
    # industry_kb_service → EmbeddingService (this module)
    # this module → industry_kb_service._embed_text
    from app.services.industry_kb_service import _embed_text as _kb_embed  # noqa: PLC0415
    return _kb_embed(session, text, timeout=timeout)


def embed_text(*, session, text: Optional[str], timeout: float = 15.0) -> Optional[List[float]]:
    """
    返回 768 维 float list, 失败/空文本返回 None。

    Args:
        session: SQLModel Session (industry_kb_service._embed_text 内部需要它读 ai_config)
        text: 待 embed 的文本
        timeout: 秒（透传给底层 _embed_text_raw）
    """
    if not text or not text.strip():
        return None
    try:
        return _embed_text_raw(session, text, timeout=timeout)
    except Exception:
        logger.exception("embed_text failed for text len=%d", len(text))
        return None
