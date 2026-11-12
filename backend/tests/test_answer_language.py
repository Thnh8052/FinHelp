"""An English question gets an English answer and a Vietnamese question a Vietnamese one (plan_guardrails_h4.md 7.3): the shared prompt holds no Vietnamese text, so
nothing is there to be copied into an English answer; both languages have a reminder on the question line. No model: only the messages are built."""
import pytest

from app.core.config import settings
from app.modules.generation import generator
from app.modules.generation.generator import LANGUAGE_VI_STRUCTURED, QUESTION_EN, SYSTEM_V4, build_messages

VIETNAMESE_LETTERS = "ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
CONTEXT = "--- Excerpt [1] (Document: X, Page: 1) ---\nRevenue 100"


@pytest.fixture(autouse=True)
def _v4(monkeypatch):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4")


def test_the_shared_prompt_holds_no_vietnamese_text_and_its_table_labels_are_english_and_neutral():
    assert not [ch for ch in SYSTEM_V4.lower() if ch in VIETNAMESE_LETTERS]
    for label in ("Ghi chú", "Chỉ tiêu", "Suncor", "Barrick"):
        assert label not in SYSTEM_V4
    assert "`*Notes:*` list (translate this label and the table headers into the question's language)" in SYSTEM_V4
    assert "| Metric | Company | FY2024 (unit) [n] | FY2025 (unit) [n] | YoY change (%) |" in SYSTEM_V4


def test_an_english_question_carries_the_english_reminder_on_its_question_line():
    system, user = (m["content"] for m in build_messages(CONTEXT, "What was Nike's revenue in fiscal 2023?"))
    assert user.endswith(f"{QUESTION_EN}What was Nike's revenue in fiscal 2023?") and "\n\nQuestion: " not in user
    assert QUESTION_EN.startswith("Question (English:") and "table headers, notes and short_answer" in QUESTION_EN
    assert LANGUAGE_VI_STRUCTURED not in system


def test_a_vietnamese_question_keeps_its_own_language_block_and_marker_and_gets_no_english_one():
    system, user = (m["content"] for m in build_messages(CONTEXT, "Doanh thu của Nike năm 2023 là bao nhiêu?"))
    assert LANGUAGE_VI_STRUCTURED in system
    assert "Question (Vietnamese — trả lời hoàn toàn bằng tiếng Việt ngay từ câu đầu tiên): Doanh thu" in user and QUESTION_EN not in user


def test_the_other_prompts_are_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v3")
    user = build_messages(CONTEXT, "What was Nike's revenue in fiscal 2023?")[1]["content"]
    assert "\n\nQuestion: What was Nike's revenue" in user and QUESTION_EN not in user
    assert generator.SYSTEM_V3  # v3 is untouched by the change
