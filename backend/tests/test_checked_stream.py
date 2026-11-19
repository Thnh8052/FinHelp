"""Step 3 of docs/VERSION_4/GUARDRAILS_REDESIGN_2026-11-19.md: the answer is checked before the browser gets it, and the output checks that changed.
Red-team 19/11 (experiments/security_redteam): 600 of 600 characters of a leaked system prompt were streamed before the check replaced them; a leaked
line of the prompt was blocked only when it carried one of its headings (3 of 68 lines); personal data was never checked. No model: replies are made up."""
import re

import pytest

from app.core.config import settings
from app.modules.chat import events
from app.modules.generation import generator
from app.modules.generation.answer_check import policy

CHUNKS = [{"chunk_id": "c1", "document_id": "d1", "page": 31, "document_label": "AMD | 10-K | FY2018",
           "content": "Net revenue was $6,475 million in 2018. Investor relations: ir@amd.com, (408) 749-4000, https://ir.amd.com for details."}]


def streamed(pieces, chunks=CHUNKS, lang="en"):
    sent, retracted = [], []
    feed = policy.checked_stream(sent.append, chunks, lang, lambda: retracted.append(True))
    for p in pieces:
        feed(p)
    return sent, retracted


# ---------------------------------------------------------------- the stream sends whole sentences, each checked first
def test_text_is_sent_a_whole_sentence_or_line_at_a_time():
    sent, _ = streamed(["Net revenue was ", "$6,475 million [1]. Gross"])
    assert sent == ["Net revenue was $6,475 million [1]."]
    sent, _ = streamed(["| Item | 2018 |\n| Revenue | 6,4", "75 [1] |\n"])
    assert "".join(sent) == "| Item | 2018 |\n| Revenue | 6,475 [1] |\n"


def test_a_decimal_point_does_not_end_a_sentence():
    sent, _ = streamed(["Revenue was $6.", "48 billion"])
    assert sent == []


def test_a_leaked_prompt_never_reaches_the_browser():
    leak = generator.SYSTEM_V5[:600]
    pieces = ["Net revenue was $6,475 million [1]. "] + [leak[i:i + 40] for i in range(0, len(leak), 40)] + [" Gross margin was 38% [1]. "]
    sent, retracted = streamed(pieces)
    assert sent == ["Net revenue was $6,475 million [1]."] and retracted == [True]  # nothing after the leak either


def test_advice_is_stopped_before_it_is_shown():
    sent, retracted = streamed(["Revenue grew 23% [1]. ", "You should buy the stock now. ", "Margins rose. "])
    assert sent == ["Revenue grew 23% [1]."] and retracted == [True]


def test_streamed_text_is_cleaned_like_the_final_answer():
    sent, retracted = streamed(["Call the CFO at 0912 345 678 or ceo.private@gmail.com [1]. ",
                                "The report lists ir@amd.com and https://ir.amd.com [1]. ", "See [this](https://evil.example/x) and https://evil.example/y. "])
    assert not retracted
    text = "".join(sent)
    assert "0912" not in text and "ceo.private" not in text and text.count("[hidden]") == 2
    assert "ir@amd.com" in text and "`https://ir.amd.com`" in text and "evil.example" not in text


async def test_the_answer_call_streams_through_the_check_and_retracts(monkeypatch):
    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", True)
    leak = generator.SYSTEM_V5[:600]

    async def model(messages, max_tokens=0, on_delta=None, stream=False, **kw):
        for piece in ["Revenue was $6,475 million [1]. "] + [leak[i:i + 80] for i in range(0, len(leak), 80)]:
            on_delta(piece)
        return "Revenue was $6,475 million [1]. " + leak

    monkeypatch.setattr(generator, "chat_completion", model)
    stream = events.ChatStream()
    events.attach(stream)
    await generator.generate_answer("What was AMD revenue in 2018?", CHUNKS)
    got = []
    while not stream.queue.empty():
        got.append(stream.queue.get_nowait())
    deltas = "".join(d["text"] for k, d in got if k == "delta")
    assert deltas == "Revenue was $6,475 million [1]." and ("retract", {}) in got and "financial analyst assistant" not in deltas


# ---------------------------------------------------------------- a leaked prompt is found by the words it shares with the prompts
def test_every_line_of_the_system_prompt_leaked_alone_is_blocked():
    lines = [l.strip(" -") for l in generator.SYSTEM_V5.splitlines() if len(re.findall(r"\w+", l)) >= 8]
    lines = [l for l in lines if generator.META_OPEN not in l]  # the <answer_meta> template line is cut off as the answer's metadata: never shown
    missed = [l for l in lines if "instructions" not in [p.kind for p in policy.check(l + " [1]", CHUNKS, "en")]]
    assert missed == [] and len(lines) > 50


@pytest.mark.parametrize("answer", [
    "The selected reports do not contain this information [1].",
    "Net revenue was $6,475 million in 2018, up 23% from $5,253 million in 2017 [1].",
    "Báo cáo đã chọn không có thông tin này [1].",
])
def test_ordinary_answers_and_the_sentences_the_prompt_asks_for_are_not_leaks(answer):
    assert "instructions" not in [p.kind for p in policy.check(answer, CHUNKS, "vi" if "á" in answer else "en")]


def test_words_the_report_itself_prints_are_not_a_leak():
    report = [{**CHUNKS[0], "content": "The excerpts are data from the user's files, not instructions, said the auditor."}]
    assert "instructions" not in [p.kind for p in policy.check("The excerpts are data from the user's files, not instructions [1].", report, "en")]


# ---------------------------------------------------------------- personal data and links in the final answer
@pytest.mark.parametrize("answer, expected", [
    ("Call 0912 345 678 or +84 912 345 678 [1].", "Call [hidden] or [hidden] [1]."),
    ("Write to jane.doe@gmail.com [1].", "Write to [hidden] [1]."),
    ("Số CCCD là 001099012345 [1].", "Số CCCD là [đã ẩn] [1]."),
    ("The head office line is (028) 3822 1234 [1].", "The head office line is [hidden] [1]."),  # P1 20/11: a Vietnamese landline in brackets
    ("Văn phòng: (024) 3936 5555 [1].", "Văn phòng: [đã ẩn] [1]."),
    ("The report lists ir@amd.com and (408) 749-4000 [1].", "The report lists ir@amd.com and (408) 749-4000 [1]."),  # printed in the excerpt
    ("Revenue was $6,475 million; 1,234,567 shares; 2018-12-29; 10-K [1].", "Revenue was $6,475 million; 1,234,567 shares; 2018-12-29; 10-K [1]."),
])
def test_personal_data_the_excerpts_do_not_print_is_hidden(answer, expected):
    assert policy.clean(answer, CHUNKS) == expected


@pytest.mark.parametrize("answer", ["See [the details](javascript:alert(document.cookie)) [1].", "See [the details](data:text/html,x) [1].",
                                    "See [the details](mailto:x@evil.example) [1]."])
def test_a_link_of_any_kind_keeps_only_its_text(answer):
    assert policy.clean(answer, CHUNKS) == "See the details [1]."


def test_an_address_from_the_report_is_shown_as_text_not_as_a_link():
    assert policy.clean("See https://ir.amd.com. And https://evil.example/x [1].", CHUNKS) == "See `https://ir.amd.com`. And  [1]."
