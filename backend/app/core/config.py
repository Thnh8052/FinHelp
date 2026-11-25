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

    # Every secret below has repr=False: printing the settings (a traceback, pytest's monkeypatch, a log line) never shows it (19/11: a test error
    # printed every key of backend/.env). tests/test_auth_security.py checks that each setting named like a secret is hidden.
    # JWT Security. SECRET_KEY has no default: the server does not start without one (and not with the .env.example placeholder
    # outside ENVIRONMENT=development).
    SECRET_KEY: str = Field(min_length=16, repr=False)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    # Password of the `admin` account: created / reset to it at startup. Unset: no admin is created and an existing one is left alone.
    ADMIN_PASSWORD: Optional[str] = Field(default=None, min_length=8, repr=False)

    # MongoDB
    MONGODB_URI: str = Field(default="mongodb://localhost:27017", repr=False)  # an Atlas address carries the password
    MONGODB_DB_NAME: str = "datn_finance"

    # Qdrant Vector Search. QDRANT_PATH (a folder) runs Qdrant embedded in-process: no Docker needed.
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_PATH: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "financial_chunks_m3"  # new name: the old 768-dim collection is left untouched
    QDRANT_API_KEY: Optional[str] = Field(default=None, repr=False)

    # Storage paths & Cloudflare R2
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_LOCAL_DIR: Path = BASE_DIR / "storage"
    PDF_STORAGE_DIR: Path = BASE_DIR / "storage" / "pdfs"
    ARTIFACTS_STORAGE_DIR: Path = BASE_DIR / "storage" / "artifacts"

    # Cloudflare R2 / S3 Object Storage
    STORAGE_BACKEND: str = "local"  # "local" | "r2"
    R2_ENDPOINT_URL: Optional[str] = Field(default=None, repr=False)  # names the Cloudflare account
    R2_ACCESS_KEY_ID: Optional[str] = Field(default=None, repr=False)
    R2_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, repr=False)
    R2_BUCKET_NAME: Optional[str] = "finhelp-storage"
    R2_PUBLIC_DOMAIN: Optional[str] = None

    # LLM Settings (DeepSeek chat-completions API)
    OPENROUTER_API_KEY: Optional[str] = Field(default=None, repr=False)
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None, repr=False)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, repr=False)
    OPENAI_API_KEY: Optional[str] = Field(default=None, repr=False)
    GEMINI_API_KEY: Optional[str] = Field(default=None, repr=False)
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
    SENDGRID_API_KEY: Optional[str] = Field(default=None, repr=False)
    SENDGRID_FROM_EMAIL: Optional[str] = "noreply@finhelp.ai"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Research core (FinanceBench 118-121/150 configuration) -----------------------------------------
    # Ingestion: Docling (TableFormer ACCURATE) + postprocess in a subprocess, or "pymupdf" for a fast, lower-quality parse.
    PARSER_ENGINE: str = "docling"
    # OCR fallback (spec L8): Docling runs with do_ocr=False, so a scanned page gives no text. Pages it reads badly (a scan, garbled text, text it lost, a table F3 could not
    # rebuild; ingestion/page_quality.py) are read again, those pages only, by the OCR backend named here (a key of page_quality.READERS). Datalab Chandra since 22/11:
    # 97.1 % of 648 true table rows on 40 scanned IFRS pages vs 92.0 % for Docling with OCR, 3 dollars per 1,000 pages (ocr_scan_2026-11-22.md). No page cap (owner 22/11).
    # No DATALAB_API_KEY: no request, Docling's pages stand.
    OCR_FALLBACK_ENABLED: bool = True
    OCR_BACKEND: str = "chandra"
    DATALAB_API_KEY: Optional[str] = Field(default=None, repr=False)
    DATALAB_MODE: str = "balanced"  # the measured mode
    # Pictures under a Docling picture box are not read by any model since 25/11 (owner, plan "parsing gọn lại"): their pages are listed as not processed
    # (ingestion/parse_check.py). The one model reader kept: image regions on a page with a text layer that no Docling picture box covers (a table pasted as a
    # picture, Enablence p42), read by the vision model with the measured prompt v2 (api_readers.REGION_PROMPT, ingestion/image_regions.py): 99.0 % of the
    # printed numbers on 30 new images, 0 of 269 invented, 0.38 dollar per 1,000 images (experiments TRIED NP-40); on the 170 PDFs the 17 NP-39 images with
    # figures 100 % of their numbers, 0 of 455 invented, 10 of 10 photos skipped (TRIED NP-46). Through the OpenAI API (OPENAI_API_KEY; none: no request).
    IMAGE_REGION_READER_ENABLED: bool = True
    FIGURE_MODEL: str = "gpt-4.1-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    API_READ_CONCURRENCY: int = 4  # requests in flight at once for one document (Chandra pages, image regions)
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
    # TK-49, chosen by the owner 17/11/2026 (docs/VERSION_4/TRIED.md TK-35, TK-44, TK-46, TK-49; CONFIG_DECISION_2026-11-17.md). On gold v2, 187 questions, the evidence is
    # complete in 89.8 % against 76.5 % for the settings before it (+26 / -1); the answers were measured on the 13,900-token version (TK-48). Its parts:
    # - the relative threshold 0.5 -> 0.2 (it was the first cause of lost evidence: a text chunk scored far below a table chunk of the same search);
    # - MULTIDOC_QUESTION_LANE_PER_DOC: one more search with the question in every planned document (dense + BM25, like a plan query), before the question search over all of them;
    # - RERANK_WINDOWS_*: a text chunk (no table) of more than RERANK_WINDOW_MIN_TOKENS stored tokens is also scored by windows of RERANK_WINDOW_WORDS words every
    #   RERANK_WINDOW_STRIDE words, and keeps its best score (a fact buried in a chunk about something else); the chunk sent is the whole chunk. About +2.4 s of reranking a question;
    # - one budget of MULTIDOC_PLANNED_MAX_TOKENS counted as the answer call counts them (MULTIDOC_TOKEN_UNIT "cl100k": cl100k of the text + EXCERPT_HEADER_TOKENS), no chunk
    #   ceiling in practice (MULTIDOC_MIN_CHUNKS 60). 13,000 keeps the answer call's input under 16,000 real tokens
    #   (2,782 tokens outside the excerpts at most, measured on 56 real calls); the real input of the heaviest questions is not yet measured.
    MULTIDOC_REL_THRESHOLD: float = 0.2
    MULTIDOC_MAX_CHUNKS: int = 10
    MULTIDOC_MIN_CHUNKS: int = 60
    MULTIDOC_CHUNKS_PER_FILE: int = 4
    MULTIDOC_QUESTION_POOL: int = 15
    MULTIDOC_QUESTION_KEEP: int = 3
    MULTIDOC_QUESTION_LANE_PER_DOC: bool = True
    # "Search deeper" keeps the excerpts the first answer cited, and after them the best of the others it was sent (in the order sent) while they use at most this share
    # of MULTIDOC_PLANNED_MAX_TOKENS; the new search takes the rest. 0 = only the cited ones stay (the rule before 20/11: C2 measured that the click then dropped the evidence
    # page of 11 of 23 answers that had it all, though the answer itself got no worse).
    DEEPER_KEEP_SENT_SHARE: float = 0.5
    MULTIDOC_MAX_TOKENS: int = 8192  # without a plan (allocate)
    MULTIDOC_PLANNED_MAX_TOKENS: int = 13000  # with a plan (planned_ceilings)
    MULTIDOC_TOKEN_UNIT: str = "cl100k"  # "cl100k": what the answer call reads; "stored": the BGE-M3 count stored with each chunk (before TK-46)
    EXCERPT_HEADER_TOKENS: int = 25  # the "--- Excerpt [n] (Document: ..., Page: ...) ---" line of each chunk in the answer call
    RERANK_WINDOWS_ENABLED: bool = True
    RERANK_WINDOW_MIN_TOKENS: int = 600  # TK-56: 400 -> 600 = 167 -> 160 pairs a question, +1/-0 on gold v2
    RERANK_WINDOW_WORDS: int = 200
    RERANK_WINDOW_STRIDE: int = 150
    # The evidence gate (L15) is gone (owner 17/11/2026, docs/VERSION_4/TRIED.md TK-55): on TK-49 it saved 1 of 187 gold questions when the planner was right
    # and 1.2 / 4.9 / 4.3 points when it was wrong, for 35 more reranker pairs a question. A missed named document is repaired by R5, the rest by the user
    # (the "understood" line and its buttons). Copies: experiments/archive/removed_gate_2026-11-17.
    # Multi-step questions (docs/VERSION_4/ROADMAP_V4.md 3.3; measured 17/11 in experiments/scripts/agentic). Both off by default: everything as before.
    # MULTIDOC_WHOLE_MESSAGE: over several sources a message of several questions is not cut at its question marks: the planner reads it whole (24 messages: evidence
    # of every part 23 against 22 when code cut it). Without a plan, code still cuts it and routes each part (R5, else R4) as the net.
    # MULTIHOP_ENABLED: over several sources a question whose second part needs the answer of the first ("which had the highest revenue, and what was its net
    # income?") is no longer refused. The planner (PROMPT_MULTIHOP) plans the first part and returns the dependent part; when that part names an item to look up,
    # one intermediate call (query_router/bridge.py) reads the first excerpts, states the result with citations and plans the second search; its new excerpts
    # follow the first ones within MULTIDOC_PLANNED_MAX_TOKENS. At most two steps. Measured: 20 two-step questions, evidence of both steps 16, correct answers 17, intermediate
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
    # V1 (a targeted document with no chunk got one more search of its own) is gone: 0 runs in 192 questions (TRIED KH-14); the answer is still told what is missing.
    # A search that times out or loses its connection to the vector store is sent again this many times after the first try, with this pause
    # between tries (chat/retrieval_step.py); still failing -> the SEARCH_UNAVAILABLE error (503) instead of INTERNAL_ERROR. 0 = no retry.
    SEARCH_RETRIES: int = 1
    SEARCH_RETRY_DELAY_SECONDS: float = 1.0
    # Deadlines (step 2 of docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md). Past PLAN_DEADLINE_SECONDS the planner (or the single-document query split) is
    # dropped and the question goes the way a failed planner goes (the longest of 200 stored planner calls took 17.0 s). Past max(RERANK_DEADLINE_SECONDS,
    # RERANK_SECONDS_PER_PAIR x pairs) the reranker is dropped and the first-stage order answers (longest measured 25.5 s for 216 pairs; 0.15 s a pair is 3x the
    # measured rate). Either is written in the result's `degraded`: the answer then shows the "search more" button prominently (TRIED TK-57: 89.3 -> 72.2 %).
    PLAN_DEADLINE_SECONDS: float = 20.0
    RERANK_DEADLINE_SECONDS: float = 30.0
    RERANK_SECONDS_PER_PAIR: float = 0.15
    # Sources a question may use, and documents a notebook may hold: a guest 1, every signed-in account (admin too) 5.
    # The one place these numbers live: TIER_SPECS, the error messages and the web app (through /auth/me) all read them from here.
    MAX_SELECTED_DOCS_GUEST: int = 1
    MAX_SELECTED_DOCS_USER: int = 5
    # What guests may spend per day, counted per IP address (raise them for a demo where everyone shares one network)
    GUEST_DAILY_NOTEBOOKS: int = 10
    GUEST_DAILY_UPLOADS: int = 10
    GUEST_DAILY_QUESTIONS: int = 30
    # Accounts one IP address may open per day (each gets its own daily questions): without it a script opened 25 accounts in a row (red-team 19/11).
    # Raise it like the guest limits for a demo where everyone registers from one network.
    REGISTRATIONS_PER_IP_DAILY: int = 10
    # Tokens every chat question of the day may spend together (UTC day; all accounts and guests; guard, planner and answer calls): past it no new question
    # starts until the next day (429 daily_budget_used). Per-account limits alone let many accounts spend without end (red-team 19/11, LLM10). A question
    # measured 19/11 used about 18,000 tokens, so 20,000,000 is about 1,100 questions, a few dollars at most. 0 = no ceiling.
    DAILY_TOKEN_BUDGET: int = 20_000_000
    # Remote GPU Worker (e.g. Google Colab / Kaggle T4 GPU via Cloudflare Tunnel)
    REMOTE_GPU_URL: Optional[str] = Field(default=None, repr=False)  # the worker has no password: whoever has the address can use it

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
    # "v5" (the default since 19/11, owner): v4.1's three fixes, rules for interim periods, amounts dated after the period end, report names and
    # statuses; measured equal to v4 on 64 questions with tidier tables (docs/VERSION_4/PROMPT_V5_DRAFT_2026-11-19.md section 5). v4 stays selectable.
    GENERATION_PROMPT: str = "v5"
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
