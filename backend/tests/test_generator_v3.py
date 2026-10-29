from app.services.rag_workflow.generator import build_messages, final_answer, is_refusal, split_answer

ANSWER = ("Air Canada had the higher revenue in 2024 [3].\n"
          '<answer_meta>{"status": "answered", "short_answer": "Air Canada, by CAD 1,651 million", "citations": [1, 3]}</answer_meta>')


def test_split_answer_removes_the_block_and_reads_it():
    text, meta = split_answer(ANSWER)
    assert text == "Air Canada had the higher revenue in 2024 [3]."
    assert meta == {"status": "answered", "short_answer": "Air Canada, by CAD 1,651 million", "citations": [1, 3], "valid": True}
    assert final_answer(ANSWER) == "Air Canada, by CAD 1,651 million" and not is_refusal(ANSWER)


def test_broken_block_counts_as_answered_with_the_written_citations():
    text, meta = split_answer("Revenue was CAD 20,604 million [2]. More text.\n<answer_meta>{not json")
    assert text == "Revenue was CAD 20,604 million [2]. More text."
    assert meta["status"] == "answered" and meta["citations"] == [2] and not meta["valid"]
    assert meta["short_answer"] == "Revenue was CAD 20,604 million [2]"


def test_not_found_is_a_refusal_and_older_answers_are_unchanged():
    nf = 'The selected reports do not contain it.\n<answer_meta>{"status": "not_found", "short_answer": "not in the reports", "citations": []}</answer_meta>'
    assert is_refusal(nf)
    v2 = "Reasoning.\nFINAL ANSWER: $5 million"
    assert split_answer(v2) == (v2, None) and final_answer(v2) == "$5 million" and not is_refusal(v2)


def test_v3_messages_have_no_language_block_and_keep_notes(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v3")
    system, user = build_messages("--- Excerpt [1] ---\nx", "Doanh thu năm 2024 là bao nhiêu?", True, ["State the assumption."])
    assert system["content"].endswith("Notes for this question:\n- State the assumption.")
    assert "LANGUAGE" not in system["content"] and "FINAL ANSWER" not in user["content"]
    assert user["content"].startswith("Excerpts from the selected reports:")


def test_v3_answer_without_its_block_counts_as_answered(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v3")
    text, meta = split_answer("Capex was USD 1,577 million [2].")
    assert text == "Capex was USD 1,577 million [2]." and meta["status"] == "answered" and meta["citations"] == [2] and not meta["valid"]
