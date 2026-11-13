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
    ENVIRONMENT: str = "production"  # safe unless a developer sets "development" in their own .env

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

    # Storage paths & Cloudflare R2
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_LOCAL_DIR: Path = BASE_DIR / "storage"
    PDF_STORAGE_DIR: Path = BASE_DIR / "storage" / "pdfs"
    ARTIFACTS_STORAGE_DIR: Path = BASE_DIR / "storage" / "artifacts"

    # Cloudflare R2 / S3 Object Storage
    STORAGE_BACKEND: str = "local"  # "local" | "r2"
    R2_ENDPOINT_URL: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: Optional[str] = "finhelp-storage"
    R2_PUBLIC_DOMAIN: Optional[str] = None

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

    # Email Service (SendGrid)
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = "noreply@finhelp.ai"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Research core (FinanceBench 118-121/150 configuration) -----------------------------------------
    # Ingestion: Docling (TableFormer ACCURATE) + postprocess in a subprocess, or "pymupdf" for a fast, lower-quality parse.
    PARSER_ENGINE: str = "docling"
    DOCLING_MODE: str = "accurate"  # "accurate" | "fast"
    DOCLING_DEVICE: str = "auto"  # auto | cuda | cpu
    DOCLING_TIMEOUT_SECONDS: int = 3600
    DOCLING_RETRIES: int = 1
    INGESTION_STALL_SECONDS: int = 7800  # a job this long without progress is failed; above DOCLING_TIMEOUT_SECONDS x (retries + 1), the longest a healthy file can stay silent
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
    # With a plan, Q13af (experiments/scripts/multi_doc_planner, dev compl 90.2, test 89.3 on the gold workspaces, no safety net): one search per
    # (query, document), 0.7 z(dense) + 0.3 z(BM25) over every chunk of its document -> top 20 -> Qwen3 order of the first 15 -> chunks >= 50% of
    # the search's best Qwen score; one more search with the question (dense over the planned documents, first MULTIDOC_QUESTION_POOL, Qwen3 by the
    # question, >= 50%, first MULTIDOC_QUESTION_KEEP) -> round robin. Chunks: max(MULTIDOC_MIN_CHUNKS, MULTIDOC_CHUNKS_PER_FILE x documents).
    # Tokens: MULTIDOC_MAX_TOKENS + 1,024 x (max(MULTIDOC_MAX_CHUNKS, 2 x searches) + 2 - MULTIDOC_MAX_CHUNKS), no upper limit: a harder question may use more.
    # Without a plan (R5, R4, V1 retry), `hybrid|item-rr15|rel50t8k`: the same with z(sparse) in place of z(BM25), no question search, 10 chunks / 8,192 tokens.
    MULTIDOC_PER_ITEM_LIMIT: int = 20
    MULTIDOC_CANDIDATE_LIMIT: int = 4096  # dense hits per search: every chunk of <= 5 documents, so the z-scores see the whole documents
    MULTIDOC_DENSE_WEIGHT: float = 0.7
    MULTIDOC_MAX_SEARCHES: int = 8  # without a plan: most (query, document) searches per question; beyond it the items are searched as written
    # With a plan: not a limit of the method (the most measured is 9), a bound on what one question can make the GPU do, because the plan comes from a model reading user text.
    MULTIDOC_SEARCH_GUARD: int = 40
    MULTIDOC_RERANK_TOP_N: int = 15  # Qwen3 reorders each search's first N; 0 or 1 turns it off
    MULTIDOC_REL_THRESHOLD: float = 0.5
    MULTIDOC_MAX_CHUNKS: int = 10
    MULTIDOC_MIN_CHUNKS: int = 12
    MULTIDOC_CHUNKS_PER_FILE: int = 4
    MULTIDOC_QUESTION_POOL: int = 15
    MULTIDOC_QUESTION_KEEP: int = 3
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
    # Safety net (stream 2), for a planner that chose the wrong documents: every selected document the plan does not search gets its own lane.
    # First stage per skipped document: dense + BM25 (as the main search) for [question x2, <= 3 plan queries x1], RRF, first NET_FIRST_STAGE of each query,
    # pool NET_POOL. Qwen3 scores each pool chunk by the question and by each plan query; a chunk's score is (1 - NET_FUSION_ALPHA) x the question's
    # + NET_FUSION_ALPHA x the highest of the plan queries' (the plan queries have no company name: they pull the statement tables up and the cover page down).
    # Chunks scoring >= NET_GATE, best first, take up to NET_EXTRA_SLOTS extra slots (token cap + 1,024 a slot).
    # The net only opens when dense_skip >= NET_OPEN_MIN_DENSE_GAP, dense_skip = the question's best dense similarity in the skipped documents minus its best in the documents
    # the plan kept (None: always open). Measured 12/11/2026 on the dev split and the four hard sets (docs/Version_3/plan_rag_improvements.md 8.8-8.13), compl when the planner
    # is wrong (dev k3 / k4 / k5, hard sets k3 / k4 / k5): this net 88.6 / 91.1 / 87.5 and 73.6 / 78.1 / 74.0; the net of 28/10 (gate 0.3, dense, the question only, 10 slots)
    # 75.7 / 78.6 / 64.3 and 49.9 / 56.2 / 35.6; plan right: no change on dev, 81.2 against 80.0 on the hard sets; it opens in about half of the right-plan questions.
    NET_ENABLED: bool = True
    NET_GATE: float = 0.15
    NET_EXTRA_SLOTS: int = 14
    NET_POOL: int = 20
    NET_FIRST_STAGE: int = 200
    NET_FUSION_ALPHA: float = 0.4
    NET_FUSION_QUERIES: int = 3
    NET_OPEN_MIN_DENSE_GAP: Optional[float] = -0.06  # -0.10 opens the net in 51 % of right-plan dev questions, -0.06 in 30 % with the same end-to-end correctness (34 of 35 answers, plan 8.18); -0.03 loses answers
    # Net called after the answer (docs/Version_3/plan_rag_improvements.md 8.16): when the first answer says it is only partial or that the excerpts do not hold the answer and the
    # planner left documents out, the net searches them (no dense-gap gate) and the answer is written once more with the new excerpts (the better of the two is kept).
    # Measured on 40 answers with no net: it flags 20 of 29 contexts that miss evidence (all 10 with every file wrong) and 0 of 11 complete ones; it cannot flag a question
    # that names no company and has lost the other company's file, which the dense-gap gate before the answer is for.
    LAZY_NET_ENABLED: bool = True
    # Evidence check (V1) on targeted documents: a document the question targets with no retrieved chunk gets one more search of its
    # own (at most V1_RETRY_CHUNKS chunks); still none -> the answer is told the source showed nothing.
    V1_RETRY_CHUNKS: int = 3
    # A search that times out or loses its connection to the vector store is sent again this many times after the first try, with this pause
    # between tries (chat/retrieval_step.py); still failing -> the SEARCH_UNAVAILABLE error (503) instead of INTERNAL_ERROR. 0 = no retry.
    SEARCH_RETRIES: int = 1
    SEARCH_RETRY_DELAY_SECONDS: float = 1.0
    MULTIDOC_CATALOG_LIMIT: int = 80  # more filings than this: skip the planner and search the whole notebook as before
    # Sources a question may use, and documents a notebook may hold: a guest 1, every signed-in account (admin too) 5.
    # The one place these numbers live: TIER_SPECS, the error messages and the web app (through /auth/me) all read them from here.
    MAX_SELECTED_DOCS_GUEST: int = 1
    MAX_SELECTED_DOCS_USER: int = 5
    # What guests may spend per day, counted per IP address (raise them for a demo where everyone shares one network)
    GUEST_DAILY_NOTEBOOKS: int = 10
    GUEST_DAILY_UPLOADS: int = 10
    GUEST_DAILY_QUESTIONS: int = 30
    # Remote GPU Worker (e.g. Google Colab / Kaggle T4 GPU via Cloudflare Tunnel)
    REMOTE_GPU_URL: Optional[str] = None

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
    ANSWER_INPUTS_REPAIR: bool = False  # H4: a wrong entry of the answer's `inputs` (value, line, period, excerpt) also triggers the one rewrite; off until measured on real answers
    # Guardrails. The intent router turns away small talk, off-topic requests, requests for advice... that the rules let through
    # (query_router/intent.py: one short encode on the embedding model, no language-model call). False = the rules alone, as measured before.
    INTENT_ROUTER_ENABLED: bool = True
    # The answer is checked before it is shown (generation/answer_check/policy.py): advice, leaked instructions, internal names, foul language.
    OUTPUT_POLICY_ENABLED: bool = True
    # The guard (query_router/guard.py): one short language-model call per message, beside the search, gives the message one label; a message
    # with a safety label (crisis, harmful, personal data, attack on the instructions, politics, personal advice) is turned away before any
    # answer is written. Measured in experiments/guardrail_eval/llm_guard_v2.py (docs/Version_3/plan_guardrails_h4.md section 6.1).
    GUARD_ENABLED: bool = True
    # The label off_topic also turns a message away, only when the rules found nothing that ties it to a report ("two keys": 0 of 234 wrongly turned away).
    GUARD_OFF_TOPIC_ENABLED: bool = True
    GUARD_TIMEOUT_SECONDS: float = 3.0  # the guard failing or taking longer lets the message through (recorded in the trace)

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
