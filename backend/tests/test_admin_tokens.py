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


# ---------------------------------------------------------------- money (Langfuse cost tracking; plan 26/11 3.1)
PRICES = {"miss": 0.30, "hit": 0.006, "out": 1.20}  # dollars per million tokens, as experiments/scripts/gold_v2/make_plans_v2.PEAK


def test_a_call_costs_its_cache_hits_misses_and_output_at_their_own_prices():
    from app.modules.admin.overview import call_cost

    assert call_cost(call("answer", 9.0, 15000, 1300, hit=5000), PRICES) == round((5000 * 0.006 + 10000 * 0.30 + 1300 * 1.20) / 1e6, 6)
    assert call_cost({"prompt_tokens": 1000, "completion_tokens": 100}, PRICES) == round((1000 * 0.30 + 100 * 1.20) / 1e6, 6)  # no cache split: all misses


def test_an_answer_costs_its_calls_or_is_estimated_from_its_tokens_when_older():
    from app.modules.admin.overview import answer_cost

    new = {"trace_info": {"llm_calls": [call("guard", 1, 700, 10), call("answer", 9, 15000, 1300, hit=5000)]}, "token_usage": {"prompt_tokens": 1}}
    old = {"token_usage": {"prompt_tokens": 10000, "completion_tokens": 1000}}  # stored before 20/11: no llm_calls
    assert answer_cost(new, PRICES) == (round((700 * 0.30 + 10 * 1.20 + 5000 * 0.006 + 10000 * 0.30 + 1300 * 1.20) / 1e6, 6), False)
    assert answer_cost(old, PRICES) == (round((10000 * 0.30 + 1000 * 1.20) / 1e6, 6), True)
    assert answer_cost({}, PRICES) == (0.0, False)  # a fixed reply


def test_costs_add_up_per_day_model_and_user():
    from datetime import datetime

    from app.modules.admin.overview import cost_rows

    answers = [
        {"created_at": datetime(2026, 11, 25, 9), "notebook_id": "nb1", "model_used": "deepseek-flash", "token_usage": {"prompt_tokens": 1_000_000}},
        {"created_at": datetime(2026, 11, 26, 9), "notebook_id": "g1", "model_used": "deepseek-flash", "token_usage": {"completion_tokens": 1_000_000}},
        {"created_at": datetime(2026, 11, 26, 10), "notebook_id": "nb1", "model_used": None},
    ]
    owners = {"nb1": {"owner_type": "user", "username": "ann"}, "g1": {"owner_type": "guest", "username": None}}
    c = cost_rows(answers, owners, PRICES)
    assert c["total_usd"] == 1.5 and c["estimated_share"] == 1.0
    assert c["per_day"] == {"2026-11-25": 0.3, "2026-11-26": 1.2}
    assert c["by_model"] == {"deepseek-flash": 1.5, None: 0.0}
    assert c["by_user"] == {"ann": 0.3, None: 1.2}
