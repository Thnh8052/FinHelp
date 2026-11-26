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
