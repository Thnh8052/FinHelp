"""O1 + plan 26/11 3.3: a 2-page file waited 1,820 s for a parse slot behind 12 others and the admin page said "processing time 1,862 s".
The waiting is now told apart from the work, on the admin page and to the user ("waiting, n files ahead"). Pure functions: no database."""
from datetime import datetime, timedelta

from app.modules.admin.overview import job_times, upload_time_summary
from app.modules.documents.documents import queue_positions


def test_the_wait_for_a_parse_slot_is_not_counted_as_processing():
    # bctc-vas.pdf, 24/11: queue_wait 0, docling_slot_wait_s 1,820.2, total 1,861.67
    assert job_times({"queue_wait": 0.0, "docling_slot_wait_s": 1820.2, "parse": 1849.41, "total": 1861.67}) == {"wait_s": 1820.2, "work_s": 41.47}
    assert job_times({"queue_wait": 2.5, "total": 90.0}) == {"wait_s": 2.5, "work_s": 87.5}  # local GPU: no slot wait
    assert job_times({}) == {"wait_s": None, "work_s": None}  # a job not finished yet


def test_the_admin_summary_gives_median_and_p90_of_wait_and_work():
    times = [{"wait_s": w, "work_s": 10.0 * (i + 1)} for i, w in enumerate([0.0, 0.0, 75.0, 300.0, 1820.0])] + [{"wait_s": None, "work_s": None}]
    s = upload_time_summary(times)
    assert s["files"] == 5 and s["wait_p50"] == 75.0 and s["work_p50"] == 30.0
    assert s["wait_p90"] == 1212.0 and s["work_p90"] == 46.0
    assert upload_time_summary([]) == {"files": 0, "wait_p50": None, "wait_p90": None, "work_p50": None, "work_p90": None}


def test_each_waiting_file_knows_how_many_files_wait_before_it():
    t0 = datetime(2026, 11, 24, 5, 20, 40)
    jobs = [{"document_id": f"d{i}", "queued_at": t0 + timedelta(seconds=i)} for i in (3, 1, 2)]
    assert queue_positions(jobs) == {"d1": 0, "d2": 1, "d3": 2}
    assert queue_positions([]) == {}


async def test_the_document_list_gives_a_waiting_file_its_place_in_the_queue(monkeypatch):
    from app.infrastructure.database import collections
    from app.modules.documents import documents as api
    from app.modules.documents.document import DocumentRecord

    def doc(i, status):
        return DocumentRecord(document_id=i, notebook_id="nb", file_name=f"{i}.pdf", file_size_bytes=1, file_path="p", status=status)

    class Repo:
        def __init__(self, db):
            pass

        async def get_by_notebook(self, notebook_id):
            return [doc("mine", "pending"), doc("done", "ready")]

    class Cursor:
        def __init__(self, rows):
            self.rows = rows

        async def to_list(self, n):
            return self.rows

    t0 = datetime(2026, 11, 24, 5, 20)
    jobs = [{"document_id": "other1", "queued_at": t0}, {"document_id": "other2", "queued_at": t0 + timedelta(seconds=1)},
            {"document_id": "mine", "queued_at": t0 + timedelta(seconds=2)}]
    db = {collections.INGESTION_JOBS_COLLECTION: type("Jobs", (), {"find": lambda self, q, p: Cursor(jobs)})()}

    async def allowed(*a):
        return None

    monkeypatch.setattr(api, "require_notebook", allowed)
    monkeypatch.setattr(api, "DocumentRepository", Repo)
    out = await api.list_documents("nb", "usr", db)
    assert [(d.document_id, d.queue_ahead) for d in out] == [("mine", 2), ("done", None)]


def test_the_place_in_the_queue_follows_the_turns_between_chats():
    # O1-b: chat A queued three files, then chat B one: B's file is second, not fourth
    t0 = datetime(2026, 11, 24, 5, 20, 40)
    jobs = [{"document_id": d, "notebook_id": nb, "queued_at": t0 + timedelta(seconds=s)}
            for d, nb, s in (("a1", "A", 0), ("a2", "A", 1), ("a3", "A", 2), ("b1", "B", 3))]
    assert queue_positions(jobs) == {"a1": 0, "b1": 1, "a2": 2, "a3": 3}
