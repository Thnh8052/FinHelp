"""A long chat is read a page at a time (system test 18/11, D7: a chat of 240 messages was drawn whole, 73,000 px). The interface asks for the
newest messages, then the ones before the oldest it shows (`before` = its message_index). Which answers a button was already used on is known from
the whole chat, not from the page: the answer of a click may sit on a newer page than the answer clicked."""
import asyncio

from app.modules.chat import chat as chat_api
from app.modules.chat.chat_models import MessageRecord
from app.modules.chat.chat_repo import ChatRepository


def _msg(i, role, **trace):
    return {"message_id": f"m{i}", "notebook_id": "nb", "message_index": i, "role": role, "content": "x", "trace_info": trace or None}


def test_the_repository_reads_the_page_before_a_message():
    repo = ChatRepository.__new__(ChatRepository)
    seen = {}

    async def find_many(query, sort_by, limit):
        seen.update(query=query, limit=limit)
        return [_msg(i, "user") for i in (9, 8)]

    repo.find_many = find_many
    page = asyncio.run(repo.get_messages("nb", limit=2, before=10))
    assert seen["query"] == {"notebook_id": "nb", "message_index": {"$lt": 10}} and seen["limit"] == 2
    assert [m.message_index for m in page] == [8, 9]  # oldest first, as before
    asyncio.run(repo.get_messages("nb", limit=2))
    assert seen["query"] == {"notebook_id": "nb"}  # no cursor: the newest messages


def test_the_endpoint_pages_and_marks_clicks_from_the_whole_chat(monkeypatch):
    chat = [_msg(0, "user"), _msg(1, "assistant", actions={"search_more": {"prominent": True}}),
            _msg(2, "user"), _msg(3, "assistant", retry_of="m1", click="deeper")]  # the click on m1 is on the newer page

    class Repo:
        def __init__(self, db):
            pass

        async def get_messages(self, notebook_id, limit=500, before=None):
            rows = [m for m in chat if before is None or m["message_index"] < before]
            return [MessageRecord(**m) for m in rows[-limit:]]

        async def retry_marks(self, notebook_id):
            return {"m1": "deeper"}

    async def allowed(db, notebook_id, user_id):
        return None

    monkeypatch.setattr(chat_api, "ChatRepository", Repo)
    monkeypatch.setattr(chat_api, "require_notebook", allowed)
    newest = asyncio.run(chat_api.get_messages("nb", limit=2, before=None, user_id="u1", db=None))
    assert [m.message_id for m in newest] == ["m2", "m3"] and [m.message_index for m in newest] == [2, 3]
    older = asyncio.run(chat_api.get_messages("nb", limit=2, before=2, user_id="u1", db=None))
    assert [m.message_id for m in older] == ["m0", "m1"]
    assert older[1].clicked == "deeper" and older[1].actions["search_more"] is None  # the button used on m1 is gone, though its answer is on the other page


def test_without_a_limit_the_whole_chat_comes_as_before(monkeypatch):
    seen = {}

    class Repo:
        def __init__(self, db):
            pass

        async def get_messages(self, notebook_id, limit=500, before=None):
            seen.update(limit=limit, before=before)
            return []

        async def retry_marks(self, notebook_id):
            return {}

    async def allowed(db, notebook_id, user_id):
        return None

    monkeypatch.setattr(chat_api, "ChatRepository", Repo)
    monkeypatch.setattr(chat_api, "require_notebook", allowed)
    asyncio.run(chat_api.get_messages("nb", user_id="u1", db=None))
    assert seen == {"limit": 500, "before": None}
