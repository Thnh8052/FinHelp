"""O1-b (docs/VERSION_4/ADMIN_INGESTION_PLAN_2026-11-26.md 1): the GPU parse slots are shared by every chat, first come first served, so one chat
uploading 13 files made a 2-page file of another wait 30 minutes. A freed slot now goes to the chats in turn (round robin, by the order they
started waiting); within one chat its files keep their order. Pure asyncio, no worker."""
import asyncio

from app.modules.ingestion.fair_slots import FairSlots


def test_a_freed_slot_goes_to_the_chats_in_turn():
    async def scenario():
        slots, served = FairSlots(1), []
        holder = slots.slot("x")
        await holder.__aenter__()  # one file of chat x is parsing

        async def upload(chat, name):
            async with slots.slot(chat):
                served.append(name)
                await asyncio.sleep(0)

        tasks = [asyncio.create_task(upload("a", n)) for n in ("a1", "a2", "a3")]
        await asyncio.sleep(0)
        tasks.append(asyncio.create_task(upload("b", "b1")))  # another chat, one small file, after the three
        await asyncio.sleep(0)
        await holder.__aexit__(None, None, None)
        await asyncio.gather(*tasks)
        return served

    assert asyncio.run(scenario()) == ["a1", "b1", "a2", "a3"]  # first come first served gave a1, a2, a3, b1


def test_a_free_slot_is_taken_at_once_and_a_cancelled_wait_takes_none():
    async def scenario():
        slots = FairSlots(1)
        first = slots.slot("a")
        await first.__aenter__()
        waiting = asyncio.create_task(slots.slot("b").__aenter__())
        await asyncio.sleep(0)
        waiting.cancel()  # the upload was deleted while it waited
        await asyncio.sleep(0)
        await first.__aexit__(None, None, None)
        again = slots.slot("c")
        await asyncio.wait_for(again.__aenter__(), timeout=1)  # the slot is free, not held by the cancelled wait
        return slots.free

    assert asyncio.run(scenario()) == 0
