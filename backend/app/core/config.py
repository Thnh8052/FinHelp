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
    # The budget is only a ceiling: the API bills the tokens generated (deepseek-flash accepts up to 384K), and the model does not reason longer because
    # the ceiling is higher. A cut reply is thrown away and asked again, so a ceiling that is too low costs more than a high one: at 8,000, 4 of 5 analysis
    # answers were cut and paid twice (about 8,000 wasted tokens, 35 to 40 s each); the longest complete reply measured was about 11,000 tokens.
    # 24,000 holds twice that, then one retry at 32,000 (14/11, owner's choice): the 784 stored answers never needed more than 16,000 tokens in one call and the two ~40k
    # records of the dev database are sums of 5 calls (the split per call is not stored), so a longer ladder (48,000, 64,000) only paid for replies that never end:
    # at most 56,000 tokens (about 0.07 dollar of output at peak price, about 4.5 minutes) instead of 136,000. A reply still cut at the ceiling is an error
    # (LLMTruncatedError) that the answer shows as a sorry for the system's limit, never as "not found".
    LLM_MIN_MAX_TOKENS: int = 24000
    LLM_MAX_TOKENS_CEILING: int = 32000

    # Email Service (SendGrid)
    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: Optional[str] = "noreply@finhelp.ai"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Research core (FinanceBench 118-121/150 configuration) -----------------------------------------
    # Ingestion: Docling (TableFormer ACCURATE) + postprocess in a subprocess, or "pymupdf" for a fast, lower-quality parse.
    PARSER_ENGINE: str = "docling"
    # OCR fallback (spec L8; stage 1 of 14/11): Docling runs with do_ocr=False, so a scanned page gives no text. Pages it reads badly (a scan, garbled text, text it lost; ingestion/
    # page_quality.py) are read again, those pages only, by an OCR backend named here (a key of page_quality.READERS; none exists until stage 2). Off until a backend is measured.
    OCR_FALLBACK_ENABLED: bool = False
    OCR_BACKEND: str = ""
    OCR_FALLBACK_MAX_PAGES: int = 30  # at most this many pages of one document are sent to the backend: the rest keep Docling's text (time and money)
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
    # Tokens: MULTIDOC_PLANNED_MAX_TOKENS, one cap (15/11: it was a formula growing with the searches, 8,192 + 1,024 per extra slot, no upper limit; measured on 192 questions the same
    # evidence is complete with 12,288 as with the formula, tokens sent 6,455 against 6,424 on average, at most 12,119; 8,192 loses 5 questions).
    # Without a plan (R5, R4, V1 retry): the same first stage (dense + BM25 since 15/11; it was z(BGE-M3 lexical weights) in place of z(BM25)), no question search, 10 chunks / 8,192 tokens.
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
    MULTIDOC_MAX_TOKENS: int = 8192  # without a plan (allocate)
    MULTIDOC_PLANNED_MAX_TOKENS: int = 12288  # with a plan (planned_ceilings)
    # Evidence gate of the planned search (hybrid_search.retrieve_planned; setting "L15" of docs/Version_3/RAG_REDESIGN_SPEC.md section 5.8, approved 16/11): the plan may
    # leave out a document the answer needs (5 of 192 gold questions). After the main vector search, code compares the best dense similarity of the question in each selected
    # document the plan did NOT search with its best in the searched ones; a document whose gap is >= GATE_OPEN_GAP is opened. A notebook holds at most
    # MAX_SELECTED_DOCS_USER (5) documents, so at most 4 are ever skipped: no cap of its own. Its GATE_POOL candidates come from the rank fusion of the question (weight 2) and the first GATE_PLAN_QUERIES plan queries, dense + BM25; the
    # reranker scores each against the question and those queries IN THE MAIN SEARCH'S CALL, score = GATE_QUESTION_WEIGHT x question + the rest x best plan query; the
    # GATE_MAX_CHUNKS best scores >= GATE_MIN_SCORE are appended after the main chunks while the context stays under GATE_MAX_TOKENS. No language-model call.
    # Measured on 192 questions (experiments/scripts/mvp/gate_strong.py): a correct plan loses nothing (+2 questions), opens on about half, tokens +38 % / +26 %;
    # with a required document dropped / swapped / all swapped the evidence is complete in 84 / 88 / 77 % (dev) and 72 / 78 / 71 % (hard) of the questions, 0 without it.
    # Time added when it opens (gate_timing.py, 2 x T4 through the tunnel): 3.5 s median on a correct plan, 5.4 s when the plan was wrong (0.062 s per pair).
    # A higher floor or fewer chunks falls under 70 % (gate_strong_floor.py). Worst case 4 documents opened = 240 pairs (about 15 s); predicted over 10 s in 52 of 737 wrong-plan
    # units with a notebook of at most 5 (gate_five_docs.py).
    GATE_ENABLED: bool = True
    GATE_OPEN_GAP: float = -0.10
    GATE_POOL: int = 15
    GATE_FIRST_STAGE: int = 200  # ranks of each query that count in the fusion
    GATE_PLAN_QUERIES: int = 3
    GATE_QUESTION_WEIGHT: float = 0.6
    GATE_MIN_SCORE: float = 0.15
    GATE_MAX_CHUNKS: int = 14
    GATE_MAX_TOKENS: int = 20480
    # Multi-step questions (docs/VERSION_4/ROADMAP_V4.md 3.3; measured 17/11 in experiments/scripts/agentic). Both off by default: everything as before.
    # MULTIDOC_WHOLE_MESSAGE: over several sources a message of several questions is not cut at its question marks: the planner reads it whole (24 messages: evidence
    # of every part 23 against 22 when code cut it). Without a plan, code still cuts it and routes each part (R5, else R4) as the net.
    # MULTIHOP_ENABLED: over several sources a question whose second part needs the answer of the first ("which had the highest revenue, and what was its net
    # income?") is no longer refused. The planner (PROMPT_MULTIHOP) plans the first part and returns the dependent part; when that part names an item to look up,
    # one intermediate call (query_router/bridge.py) reads the first excerpts, states the result with citations and plans the second search; its new excerpts
    # follow the first ones within GATE_MAX_TOKENS. At most two steps. Measured: 20 two-step questions, evidence of both steps 16, correct answers 17, intermediate
    # result right 19; on gold v2 the prompt kept the evidence (147 of 187 against 143). The call takes 5.2 s median; past the deadline the first step counts as unsettled.
    MULTIDOC_WHOLE_MESSAGE: bool = False
    MULTIHOP_ENABLED: bool = False
    MULTIHOP_BRIDGE_TIMEOUT_SECONDS: float = 10.0
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
    # Evidence check (V1) on targeted documents: a document the question targets with no retrieved chunk gets one more search of its
    # own (at most V1_RETRY_CHUNKS chunks); still none -> the answer is told the source showed nothing.
    V1_RETRY_CHUNKS: int = 3
    # A search that times out or loses its connection to the vector store is sent again this many times after the first try, with this pause
    # between tries (chat/retrieval_step.py); still failing -> the SEARCH_UNAVAILABLE error (503) instead of INTERNAL_ERROR. 0 = no retry.
    SEARCH_RETRIES: int = 1
    SEARCH_RETRY_DELAY_SECONDS: float = 1.0
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
    # "v4_1" is v4 with three self-contradictions fixed (citation in table cells, two decimals for ratios, no space-grouped example cell);
    # it stays off until measured on questions it was not designed with.
    GENERATION_PROMPT: str = "v4"
    # A2: an answer with a figure the excerpts do not show, a citation to no excerpt or to another company / period is rewritten once
    # with the list of problems; what is still wrong after that is flagged in the answer ("chưa kiểm chứng"), never silently kept.
    ANSWER_REPAIR_ENABLED: bool = True
    # Guardrails. The intent router turns away small talk, off-topic requests, requests for advice... that the rules let through
    # (query_router/intent.py: one short encode on the embedding model, no language-model call). False = the rules alone, as measured before.
    INTENT_ROUTER_ENABLED: bool = True
    # The answer is checked before it is shown (generation/answer_check/policy.py): advice, leaked instructions, internal names, foul language.
    OUTPUT_POLICY_ENABLED: bool = True
    # The guard (query_router/guard.py): one short language-model call per message, beside the search, gives the message one label; a message
    # with a safety label (crisis, harmful, personal data, attack on the instructions, politics, personal advice) is turned away before any
    # answer is written. Measured in experiments/guardrail_eval/llm_guard_v2.py (docs/Version_2/plans/plan_guardrails_h4.md section 6.1).
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
