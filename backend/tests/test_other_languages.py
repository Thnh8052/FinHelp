"""A question in a language other than Vietnamese or English gets one fixed reply in both languages (owner 19/11). Before: French and Spanish read
as Vietnamese (their accents "é", "á" are Vietnamese letters too) and were answered in Vietnamese; Chinese, Russian and German read as English."""
import pytest

from app.modules.query_router.input_policy import SourceInfo, decide, unsupported_language
from tests.test_input_policy import NIKE_DOCS, _orchestrator

SRC = [SourceInfo("Amazon.com, Inc.", "10-K", 2019, None, "Amazon.com, Inc. 10-K FY2019", years_covered=[2019, 2018, 2017])]
VI_LINE = "Hệ thống hiện chỉ hỗ trợ tiếng Việt và tiếng Anh"
EN_LINE = "FinHelp currently supports only Vietnamese and English"

OTHER = [
    "亚马逊2019年的收入是多少？",  # Chinese
    "Amazonの2019年の売上高はいくらですか？",  # Japanese
    "아마존의 2019년 매출은 얼마입니까?",  # Korean
    "Какой была выручка Amazon в 2019 году?",  # Russian
    "ما هي إيرادات أمازون في عام 2019؟",  # Arabic
    "รายได้ของ Amazon ในปี 2019 เป็นเท่าไหร่",  # Thai
    "Quel était le chiffre d'affaires d'Amazon en 2019 ?",  # French
    "¿Cuáles fueron los ingresos de Amazon en 2019?",  # Spanish
    "Wie hoch war der Umsatz von Amazon im Jahr 2019?",  # German
    "Qual foi a receita da Amazon em 2019?",  # Portuguese
    "Qual è stato il fatturato di Amazon nel 2019?",  # Italian
    "Berapa pendapatan Amazon pada tahun 2019?",  # Indonesian
]
OURS = [
    "What was Amazon's revenue in 2019?",
    "Doanh thu của Amazon năm 2019 là bao nhiêu?",
    "doanh thu cua amazon nam 2019 la bao nhieu",  # Vietnamese typed without accents
    "con amazon thi sao, em muon hoi ve loi nhuan nam 2019",
    "What was Alibaba (阿里巴巴) revenue compared with Amazon in 2019?",  # a name in another script inside an English question
    "Doanh thu của Nestlé và Amazon năm 2019 so với nhau thế nào?",
    "What does the line 'Umsatzerlöse' mean in the 2019 report of Amazon?",  # one foreign word, quoted
    "Is Amazon's revenue per share in 2019 higher than its 2018 figure de facto?",
    "Amazon la gi? Cho toi biet doanh thu nam 2019",
]


@pytest.mark.parametrize("question", OTHER)
def test_another_language_gets_the_fixed_reply_in_both_languages(question):
    assert unsupported_language(question)
    d = decide(question, SRC, 1)
    assert d.action == "unsupported_language" and VI_LINE in d.message and EN_LINE in d.message


@pytest.mark.parametrize("question", OURS)
def test_vietnamese_and_english_questions_are_not_turned_away(question):
    assert not unsupported_language(question)
    assert decide(question, SRC, 1).action != "unsupported_language"


def test_the_interface_language_comes_first():
    assert decide(OTHER[0], SRC, 1, ui_lang="en").message.startswith(EN_LINE)
    assert decide(OTHER[0], SRC, 1, ui_lang="vi").message.startswith(VI_LINE)


def test_the_reply_comes_before_the_source_checks():
    assert decide(OTHER[6], [], 0).action == "unsupported_language"  # no source yet: the user could not read "upload a report" either


async def test_the_chat_answers_another_language_without_searching(monkeypatch):
    orch, seen = _orchestrator(NIKE_DOCS, monkeypatch)
    r = await orch.execute_query("Quel était le chiffre d'affaires de Nike en 2019 ?", "nb", document_ids=["d1", "d2"])
    assert r["intent"] == "unsupported_language" and VI_LINE in r["answer"] and EN_LINE in r["answer"]
    assert not orch.hybrid_search.calls and "answers" not in seen
