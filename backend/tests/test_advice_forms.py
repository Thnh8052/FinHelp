"""The advice check reads the forms advice takes, not a list of phrases (19/11). Measured before the change (experiments/scripts/system_test_18_11/advice_eval.py):
on 40 advice sentences written before the change and never used to write it, the phrase list caught 0/20 English and 1/20 Vietnamese ones, while it
reported no stored answer (0/770), no chat answer and no report sentence (0/51,826).

Forms: telling the reader or investors to act; an imperative that opens with an investment act; the right time or chance to act; the stock judged as
an investment for a portfolio; a forecast of the share price; an investment act judged ("buying now is sensible"). The sentences below are the tuning
set; the held-out set stays in advice_eval.py."""
import pytest

from app.modules.generation.answer_check import policy


def advice(sentence, lang):
    return [p.kind for p in policy.check("Costco's net sales were $149,351 million in FY2019 [1]. " + sentence, [], lang)] == ["advice"]


@pytest.mark.parametrize("sentence", [
    "Investors should hold the stock through 2025.",
    "The stock looks cheap at these levels; accumulating could pay off.",
    "This is a good time to buy Costco.",
    "I would add Costco to a long-term portfolio.",
    "The valuation makes it an attractive entry point.",
    "Buying now could deliver solid returns.",
])
def test_english_advice_in_its_usual_forms_is_caught(sentence):
    assert advice(sentence, "en")


@pytest.mark.parametrize("sentence", [
    "Đây là thời điểm tốt để gom cổ phiếu này.",
    "Cổ phiếu này có tiềm năng tăng giá mạnh trong năm tới.",
    "Nên chốt lời trước kỳ báo cáo.",
    "Mua lúc này có thể mang lại lợi nhuận tốt.",
])
def test_vietnamese_advice_in_its_usual_forms_is_caught(sentence):
    assert advice(sentence, "vi")


@pytest.mark.parametrize("sentence, lang", [
    ("Whether the stock is a good investment is not something the reports say.", "en"),
    ("Báo cáo không nói cổ phiếu này có đáng mua hay không.", "vi"),
    ("Holders of the notes may require the company to buy them back [1].", "en"),
    ("The report warns that the stock price could decline if margins fall [1].", "en"),
    ("Net cash used in investing activities was $3,891 million [1].", "en"),
    ("Employees can buy shares through the purchase plan at a discount [1].", "en"),
    ("Doanh thu tăng nên công ty đầu tư thêm vào hệ thống kho [1].", "vi"),
    ("Số lượng cổ phiếu sẽ tăng nếu công ty phát hành thêm [1].", "vi"),
    ("Công ty có thể mua lại cổ phiếu theo chương trình đã công bố [1].", "vi"),
    ("Việc đầu tư vào kho mới được kỳ vọng sẽ mang lại lợi nhuận, theo ban lãnh đạo [1].", "vi"),
    # dev chat answers reported by the first version of the forms (19/11)
    ("I can provide figures and analysis from the selected reports so you can form your own view.", "en"),
    ("Tôi chỉ trả lời dựa trên các nguồn bạn chọn, không đưa lời khuyên đầu tư.", "vi"),
    ("Các con số này không phải là lời khuyên đầu tư.", "vi"),
    # a disclaimer was blocked as advice before 19/11 (a hard finding: the whole answer replaced); a company named Best Buy
    ("Câu trả lời này chỉ dựa trên báo cáo, không phải khuyến nghị mua bán.", "vi"),
    ("Competitors include Walgreens and Best Buy [1].", "en"),
])
def test_report_facts_and_declining_to_advise_are_not_advice(sentence, lang):
    assert not advice(sentence, lang)
