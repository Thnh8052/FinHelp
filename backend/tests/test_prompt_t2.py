"""T2 of the 18/11 handoff, approved by the owner 18/11: two lines of the answer prompt (v4).
  D3   a Vietnamese answer copied report figures in English format ("3,624" = thousands) and wrote its own in Vietnamese format ("3,12%"): one
       number format for the whole answer, the excerpts' English one (experiment 18/11: decimal commas 11 -> 0, no slower). The table example
       cell `52 377 [1]` (space-grouped) becomes `52,377 [1]`.
  4.8  a question that gives its own formula, definition or components: those replace the standard formula; a missing component is named, a
       substitute is called one, and a metric with several definitions says which one was used.
No model: only the prompt text and the messages."""
from app.core.config import settings
from app.modules.generation.generator import LANGUAGE_VI_STRUCTURED, SYSTEM_V3, SYSTEM_V4, SYSTEM_V4_1, build_messages

NUMBERS = ("Numbers: write every number in the English format of the excerpts — a comma for thousands and a period for decimals (3,624; 3.12%; 386.1) — "
           "in every part of the answer, including the figures you calculate. Never use a comma as the decimal mark.")
DERIVE = "- If a metric is not reported directly, derive it from its components with the standard formula and name the line items you used."
FORMULA = ("- If the question gives its own formula, definition or components, use exactly those: they replace the standard formula. Give the result in "
           "the form the question asks (ratio or percent, rounding). If one of the components is not in the excerpts, say which one is missing; do not "
           "silently replace it with another line item (if you use a close substitute, name it as a substitute). When a metric has several common "
           "definitions and the question does not choose, say in a few words which one you used.")


def _system(question, monkeypatch, prompt="v4"):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", prompt)
    return build_messages("[1] Revenue 2024 25,785", question)[0]["content"]


def test_a_vietnamese_answer_writes_every_number_in_the_excerpts_english_format(monkeypatch):
    assert LANGUAGE_VI_STRUCTURED.endswith(NUMBERS)
    assert NUMBERS in _system("Doanh thu của AMD năm 2024 là bao nhiêu?", monkeypatch)
    assert "Numbers:" not in _system("What was AMD's revenue in 2024?", monkeypatch)  # an English answer already does


def test_the_table_example_cell_uses_the_english_format():
    assert "`52,377 [1]`, `16,956 [2]`, `PwC [4]`" in SYSTEM_V4 and "52 377" not in SYSTEM_V4


def flat(text):
    """The prompt wraps a long rule over lines indented by two spaces; the words are what the model reads."""
    return " ".join(text.split())


def test_a_formula_the_question_gives_replaces_the_standard_one_in_both_languages(monkeypatch):
    assert flat(DERIVE + " " + FORMULA) in flat(SYSTEM_V4)
    assert flat(FORMULA) in flat(SYSTEM_V4_1)  # v4.1 is built from v4
    assert flat(FORMULA) not in flat(SYSTEM_V3)
    for question in ("Define ROE as net income / average equity and compute it for AMD in 2024.", "Tính ROE của AMD năm 2024 theo định nghĩa lợi nhuận ròng / vốn chủ sở hữu bình quân."):
        assert flat(FORMULA) in flat(_system(question, monkeypatch))
