import asyncio
from pathlib import Path
import sys

# Thêm thư mục backend vào sys.path để luôn tìm thấy module 'app'
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.core.logging import logger
from app.core.security import get_password_hash
from app.db.mongodb import MongoManager
from app.db.repositories.notebook_repo import NotebookRepository
from app.db.repositories.user_repo import UserRepository
from app.models.notebook import NotebookRecord
from app.models.user import UserRecord


async def seed():
    await MongoManager.connect_to_database()
    db = MongoManager.db
    if db is None:
        return

    user_repo = UserRepository(db)
    notebook_repo = NotebookRepository(db)

    # 1. Tài khoản Quản trị viên: Vũ Thành (role='admin', tier='user', max 5 docs/notebook)
    existing_user = await user_repo.get_by_username("analyst_demo")
    standard_user_quota = {
        "tier": "user",
        "daily_messages_limit": 100,
        "messages_used_today": 0,
        "max_upload_documents": 5,
        "max_file_size_mb": 20,
        "total_tokens_consumed": 12500,
        "total_cost_usd": 0.045,
    }

    if not existing_user:
        demo_user = UserRecord(
            user_id="usr_vuthanh_01",
            email="vuthanh@finanalyst.ai",
            username="analyst_demo",
            hashed_password=get_password_hash("FinAnalyst2026!"),
            full_name="Vũ Thành - Chuyên Viên & Quản Trị Hệ Thống",
            role="admin",
            quota=standard_user_quota,
        )
        await user_repo.save_user(demo_user)
        logger.info("Admin user 'analyst_demo' (Vũ Thành) seeded.")
    else:
        await user_repo.collection.update_one(
            {"user_id": existing_user.user_id},
            {
                "$set": {
                    "full_name": "Vũ Thành - Chuyên Viên & Quản Trị Hệ Thống",
                    "role": "admin",
                    "quota": standard_user_quota,
                }
            },
        )
        logger.info("Admin user 'analyst_demo' updated for Vũ Thành.")

    # 2. Tài khoản Người dùng thông thường (Free Tier)
    existing_free_user = await user_repo.get_by_username("user_free")
    if not existing_free_user:
        free_user = UserRecord(
            user_id="usr_free_01",
            email="member@finanalyst.ai",
            username="user_free",
            hashed_password=get_password_hash("FinAnalystFree2026!"),
            full_name="Nguyễn Văn A - Người Dùng Trải Nghiệm",
            role="user",
        )
        await user_repo.save_user(free_user)
        logger.info("Standard Free user 'user_free' seeded.")


    existing_nb = await notebook_repo.get_by_id("nb_demo_001")
    if not existing_nb:
        demo_nb = NotebookRecord(
            notebook_id="nb_demo_001",
            user_id="usr_demo_001",
            title="Coca-Cola (KO) vs PepsiCo (PEP) — SEC Form 10-K Analysis",
            description="Comparative analysis of Gross Margin, Operating Cash Flow, and Debt-to-Equity ratios.",
            tags=["KO", "PEP", "SEC 10-K", "US GAAP", "Beverages"],
        )
        await notebook_repo.save_notebook(demo_nb)
        logger.info("Demo notebook 'nb_demo_001' (SEC 10-K) seeded.")

    # 3. Không gian phân tích Notebook & Phiên Chat cho Quản Trị Viên (Vũ Thành) - SEC 10-K Filings
    from app.db.repositories.chat_repo import ChatRepository
    from app.models.chat import ChatSessionRecord, MessageRecord

    chat_repo = ChatRepository(db)
    vuthanh_nb = await notebook_repo.get_by_id("nb_vuthanh_01")
    if not vuthanh_nb:
        nb_vt = NotebookRecord(
            notebook_id="nb_vuthanh_01",
            user_id="usr_vuthanh_01",
            title="Microsoft Corporation (MSFT) — SEC Form 10-K Analysis",
            description="Deep financial analysis on Cloud segment growth, Operating Margin, and Free Cash Flow.",
            tags=["MSFT", "SEC 10-K", "US GAAP", "FY2023"],
            document_ids=["MICROSOFT_2023_10K.pdf"],
        )
        await notebook_repo.save_notebook(nb_vt)
        logger.info("Notebook 'nb_vuthanh_01' (Microsoft SEC 10-K) seeded.")
    else:
        await notebook_repo.collection.update_one(
            {"notebook_id": "nb_vuthanh_01"},
            {
                "$set": {
                    "title": "Microsoft Corporation (MSFT) — SEC Form 10-K Analysis",
                    "description": "Deep financial analysis on Cloud segment growth, Operating Margin, and Free Cash Flow.",
                    "tags": ["MSFT", "SEC 10-K", "US GAAP", "FY2023"],
                    "document_ids": ["MICROSOFT_2023_10K.pdf"],
                }
            },
        )

    vuthanh_ses = await chat_repo.get_session("ses_vuthanh_01")
    if not vuthanh_ses:
        ses_vt = ChatSessionRecord(
            session_id="ses_vuthanh_01",
            notebook_id="nb_vuthanh_01",
            user_id="usr_vuthanh_01",
            title="Operating Margin & Revenue Growth Comparison (FY2023)",
        )
        await chat_repo.save_session(ses_vt)

        # User Query
        await chat_repo.append_message(
            MessageRecord(
                message_id="msg_vt_001",
                session_id="ses_vuthanh_01",
                role="user",
                content="What was Microsoft's Operating Margin in FY2023 according to Form 10-K, and how does it compare to FY2022?",
            )
        )
        # Assistant Answer (US GAAP Financial Calculation)
        await chat_repo.append_message(
            MessageRecord(
                message_id="msg_vt_002",
                session_id="ses_vuthanh_01",
                role="assistant",
                content=(
                    "According to **Microsoft Corporation's Form 10-K** filed with the U.S. Securities and Exchange Commission (SEC) for the fiscal year ended June 30, 2023:\n\n"
                    "### 1. Key Income Statement Metrics (Item 8 - Consolidated Financial Statements)\n"
                    "- **Total Revenue (FY2023):** $211,915 million (up 6.9% from $198,270 million in FY2022)\n"
                    "- **Operating Income (FY2023):** $88,523 million (up 6.2% from $83,383 million in FY2022)\n\n"
                    "### 2. Operating Margin Calculation\n"
                    "$$\\text{Operating Margin}_{FY2023} = \\frac{\\text{Operating Income}}{\\text{Total Revenue}} = \\frac{88,523}{211,915} \\approx 41.77\\%$$\n"
                    "$$\\text{Operating Margin}_{FY2022} = \\frac{83,383}{198,270} \\approx 42.06\\%$$\n\n"
                    "### 3. Financial Commentary & Variance Analysis\n"
                    "- **Margin Variance:** Operating margin contracted slightly by **29 basis points (bps)** from 42.06% to 41.77%.\n"
                    "- **Key Drivers:** Sustained expansion in Intelligent Cloud (Azure revenue growth +27% CC) partially offset by increased headcount costs and accelerated capital expenditures in AI infrastructure."
                ),
                citations=[
                    {
                        "citation_id": "cit_msft_01",
                        "chunk_id": "chk_msft_item8_01",
                        "document_id": "MICROSOFT_2023_10K.pdf",
                        "page": 64,
                        "table_id": "income_statement_p64",
                        "row_label": "Operating income",
                        "column_label": "Year Ended June 30, 2023",
                        "snippet": "Operating income: $88,523 million; Total revenue: $211,915 million",
                        "score": 0.94,
                    }
                ],
                trace_info={"intent": "financial_calculation", "status": "verified"},
            )
        )
        logger.info("Chat session 'ses_vuthanh_01' (SEC Form 10-K) seeded for Vũ Thành.")

    await MongoManager.close_database_connection()


if __name__ == "__main__":
    asyncio.run(seed())
