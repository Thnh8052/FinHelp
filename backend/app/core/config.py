import os
# PyTorch CUDA Allocator: chong phan manh VRAM va tu dong nha cache tren Windows
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128,garbage_collection_threshold:0.8")
from pathlib import Path
from typing import List, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Server Info
    PROJECT_NAME: str = "DATN Finance - Financial RAG System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # JWT Security. SECRET_KEY has no default: the server does not start without one (and not with the .env.example placeholder
    # outside ENVIRONMENT=development).
    SECRET_KEY: str = Field(min_length=16)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    # Password of the `admin` account: created / reset to it at startup. Unset: no admin is created and an existing one is left alone.
    ADMIN_PASSWORD: Optional[str] = Field(default=None, min_length=8)

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "datn_finance"

    # Qdrant Vector Search. QDRANT_PATH (a folder) runs Qdrant embedded in-process: no Docker needed.
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_PATH: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "financial_chunks_m3"  # new name: the old 768-dim collection is left untouched
    QDRANT_API_KEY: Optional[str] = None

    # Storage paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_LOCAL_DIR: Path = BASE_DIR / "storage"
    PDF_STORAGE_DIR: Path = BASE_DIR / "storage" / "pdfs"
    ARTIFACTS_STORAGE_DIR: Path = BASE_DIR / "storage" / "artifacts"

    # LLM Settings (DeepSeek chat-completions API)
    OPENROUTER_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    DEFAULT_LLM_MODEL: str = "deepseek-flash"
    LLM_BASE_URL: str = "https://api.deepseek.com"
    # deepseek-flash reasons before answering and its reasoning counts against max_tokens: every call gets at least this budget,
    # and a reply cut by the budget is retried with a larger one (up to LLM_MAX_TOKENS_CEILING) instead of being read as empty.
    LLM_MIN_MAX_TOKENS: int = 8000
    LLM_MAX_TOKENS_CEILING: int = 32000

    # --- Research core (FinanceBench 118-121/150 configuration) -----------------------------------------
    # Ingestion: Docling (TableFormer ACCURATE) + postprocess in a subprocess, or "pymupdf" for a fast, lower-quality parse.
    PARSER_ENGINE: str = "docling"
    DOCLING_DEVICE: str = "auto"  # auto | cuda | cpu
    DOCLING_TIMEOUT_SECONDS: int = 3600
    DOCLING_RETRIES: int = 1
    CHUNK_TOKENS: int = 1024  # page-bounded structure-aware chunks (st1024)

    # Retrieval: BGE-M3 dense -> RRF(question x2 + first N keyword sub-queries) -> pool 20 -> Qwen3 reranker fusion -> top 6
    DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_FP16_DIR: str = str(BASE_DIR / "storage" / "models" / "bge-m3-fp16")  # fp16 safetensors copy of BGE-M3; empty or missing = load DEFAULT_EMBEDDING_MODEL from the hub
    EMBEDDING_DIM: int = 1024
    EMBEDDING_MAX_LENGTH: int = 1280
    QUERY_MAX_LENGTH: int = 512
    RERANKER_MODEL: str = "Qwen/Qwen3-Reranker-0.6B"
    RERANKER_LOCAL_DIR: str = str(BASE_DIR / "storage" / "models" / "qwen3-reranker-0.6b")  # local safetensors copy; empty or missing = load RERANKER_MODEL from hub
    RERANK_ENABLED: bool = True
    SUBQUERY_COUNT: int = 3
    FIRST_STAGE_LIMIT: int = 200
    RETRIEVAL_POOL_SIZE: int = 20
    RETRIEVAL_TOP_K: int = 6
    # Several filings in one notebook (no document selected): an LLM plans one query per (filing, item) from the catalog of
    # filings, each query is searched inside its own filings and the results take equal slots (round robin).
    MULTIDOC_ENABLED: bool = True
    MULTIDOC_MAX_SUBQUERIES: int = 8
    # `hybrid|item-rr15|rel50t8k` (multi-doc dev compl 83.9 / test 71.9; 80.5 dev with the neutral reranker instruction): per search,
    # 0.7 z(dense) + 0.3 z(sparse) over every chunk of its documents -> top 20 -> Qwen3 order of the first 15 -> chunks >= 50% of the
    # search's best Qwen score -> round robin, at most 10 chunks / 8,192 tokens
    MULTIDOC_PER_ITEM_LIMIT: int = 20
    MULTIDOC_CANDIDATE_LIMIT: int = 4096  # dense hits per search: every chunk of <= 5 documents, so the z-scores see the whole documents
    MULTIDOC_DENSE_WEIGHT: float = 0.7
    MULTIDOC_MAX_SEARCHES: int = 8  # most (query, document) searches per question; beyond it the plan is searched per query
    MULTIDOC_RERANK_TOP_N: int = 15  # Qwen3 reorders each search's first N; 0 or 1 turns it off
    MULTIDOC_REL_THRESHOLD: float = 0.5
    MULTIDOC_MAX_CHUNKS: int = 10
    MULTIDOC_MAX_TOKENS: int = 8192
    # Catalog line read at upload (services/ingestion/catalog.py): the measured prompt through the DeepSeek API ("deepseek", no GPU,
    # runs while Docling parses the next file) or the local model through Ollama ("ollama"); off or unreachable -> rule header
    CATALOG_ENABLED: bool = True
    CATALOG_BACKEND: str = "deepseek"
    CATALOG_OLLAMA_URL: str = "http://127.0.0.1:11434"
    CATALOG_MODEL: str = "qwen3:4b-instruct"
    CATALOG_NUM_CTX: int = 12288
    CATALOG_NUM_GPU: int = 99
    CATALOG_TIMEOUT_SECONDS: int = 300
    # Paid fallback: the language model reads images of pages 1-2 when the local catalog is missing or its name / period is
    # unverified (a name only in a logo, no GPU / Ollama). One call per such document.
    CATALOG_VLM_ENABLED: bool = True
    # Safety net (stream 2) when the planner chooses the documents (the question names no company): every selected document the
    # plan does not search gets the single-document lane with the planner's own queries (dense RRF [question x2, plan queries x1],
    # first NET_FIRST_STAGE of each, pool NET_POOL, Qwen3 by the question); chunks with P(yes) >= NET_GATE take up to
    # NET_EXTRA_SLOTS extra slots (token cap + 1,024 a slot). Measured (version_control 218, "C1-S planner Ga30 +10"): no change when
    # the plan is right (92.4 / 83.9), one filing missed 91.4 / 73.8, every filing wrong 87.3 / 66.9 (gold / SEC dev).
    NET_ENABLED: bool = True
    NET_GATE: float = 0.3
    NET_EXTRA_SLOTS: int = 10
    NET_POOL: int = 20
    NET_FIRST_STAGE: int = 200
    # Evidence check (V1) on targeted documents: a document the question targets with no retrieved chunk gets one more search of its
    # own (at most V1_RETRY_CHUNKS chunks); still none -> the answer is told the source showed nothing.
    V1_RETRY_CHUNKS: int = 3
    MULTIDOC_CATALOG_LIMIT: int = 80  # more filings than this: skip the planner and search the whole notebook as before
    # Sources a question may use (the upload limit per notebook is the same): a guest 1, a signed-in user 5
    MAX_SELECTED_DOCS_GUEST: int = 1
    MAX_SELECTED_DOCS_USER: int = 5
    DEVICE: str = "auto"  # auto | cuda | cpu, for the embedding and reranker models
    # auto: both models stay on the GPU until the first out-of-memory error, then they take turns (small cards);
    # swap: always take turns; resident: never swap (fail on out-of-memory)
    GPU_MODE: str = "auto"
    # True: load BGE-M3 + Qwen3 at startup and after each ingestion batch (services/retrieval/warmup.py). Off since 2026-10-28:
    # each model loads on first use, so the server starts without them (a machine short of commit memory crashed in the warm-up).
    PRELOAD_MODELS: bool = False
    # Share of the card the in-process models may use. Past the dedicated VRAM Windows spills silently into shared system RAM
    # (no out-of-memory error, everything crawls), so the swap above would never trigger; the cap turns that into an error it handles.
    GPU_MEMORY_FRACTION: float = 0.85

    # Generation: prompt "v2" is the measured one (121/150). "v1" is the stricter, refusal-prone prompt (118/150).
    GENERATION_PROMPT: str = "v4"
    # A2: an answer with a figure the excerpts do not show, a citation to no excerpt or to another company / period is rewritten once
    # with the list of problems; what is still wrong after that is flagged in the answer ("chưa kiểm chứng"), never silently kept.
    ANSWER_REPAIR_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _real_secret_outside_development(self):
        if self.ENVIRONMENT != "development" and self.SECRET_KEY.startswith(("change_this", "development_secret")):
            raise ValueError("SECRET_KEY is still a placeholder: set a random value (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`).")
        return self


settings = Settings()
