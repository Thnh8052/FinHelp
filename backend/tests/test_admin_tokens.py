"""The admin tokens page (UI check 26/11, U1): answers that called no model (fixed replies) are not an "unknown" model, and the top users are counted in
the same window of days as the rest of the page, not over all time. Pure functions over the aggregation rows: no database."""
from app.modules.admin.overview import model_rows, top_users


def test_answers_without_a_model_call_are_not_an_unknown_model():
    rows = [{"_id": "deepseek-flash", "questions": 267, "tokens": 2782149}, {"_id": None, "questions": 37, "tokens": 0}]
    assert model_rows(rows) == [{"model": "deepseek-flash", "questions": 267, "tokens": 2782149}, {"model": None, "questions": 37, "tokens": 0}]


def test_top_users_add_up_their_notebooks_in_the_window_with_guests_as_one_row():
    rows = [{"_id": "nb1", "tokens": 500}, {"_id": "nb2", "tokens": 300}, {"_id": "nb3", "tokens": 900}, {"_id": "g1", "tokens": 40},
            {"_id": "g2", "tokens": 60}, {"_id": "nb4", "tokens": 0}, {"_id": "gone", "tokens": 10}]
    owners = {"nb1": {"owner_type": "user", "username": "ann"}, "nb2": {"owner_type": "user", "username": "ann"},
              "nb3": {"owner_type": "user", "username": "bob"}, "g1": {"owner_type": "guest", "username": None},
              "g2": {"owner_type": "guest", "username": None}, "nb4": {"owner_type": "user", "username": "cid"}}
    assert top_users(rows, owners) == [{"username": "bob", "tokens": 900}, {"username": "ann", "tokens": 800}, {"username": None, "tokens": 100}]  # "gone": deleted
    assert len(top_users([{"_id": f"n{i}", "tokens": i + 1} for i in range(12)], {f"n{i}": {"owner_type": "user", "username": f"u{i}"} for i in range(12)})) == 8


# ---------------------------------------------------------------- by purpose (Langfuse groups usage by observation name; plan 26/11 3.2)
def call(purpose, seconds, prompt, completion, status="ok", hit=0):
    return {"purpose": purpose, "seconds": seconds, "status": status, "prompt_tokens": prompt, "completion_tokens": completion,
            "prompt_cache_hit_tokens": hit, "prompt_cache_miss_tokens": prompt - hit}


def test_model_calls_add_up_per_purpose_with_their_share_of_tokens_most_tokens_first():
    from app.modules.admin.overview import purpose_rows

    traces = [{"llm_calls": [call("guard", 1.0, 700, 10), call("plan", 2.0, 1200, 200), call("answer", 9.0, 15000, 1300)]},
              {"llm_calls": [call("guard", 3.0, 800, 10, status="cancelled"), call("answer", 11.0, 14000, 1200)]},
              {"intent": "greeting"}]  # an answer stored before 20/11 or without a model call adds nothing
    rows = purpose_rows(traces)
    assert [r["purpose"] for r in rows] == ["answer", "guard", "plan"]  # guard 1,520 tokens, plan 1,400
    answer, guard = rows[0], rows[1]
    assert answer["calls"] == 2 and answer["tokens"] == 31500 and answer["prompt_tokens"] == 29000 and answer["completion_tokens"] == 2500
    assert answer["share"] == round(31500 / (31500 + 1400 + 1520), 3)
    assert guard["calls"] == 2 and guard["failed"] == 1 and guard["seconds_p50"] == 2.0 and guard["seconds_p90"] == 2.8
    assert purpose_rows([]) == []
