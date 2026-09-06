"""
Regression tests for the Fix 4 hostile-review blocker: correctness-
critical case/transaction reads must not silently depend on which API
replica happens to handle a request.

These simulate two API replicas directly at the pipeline level (each
with its own independent `store` dict, exactly as two separate FastAPI
processes would each have their own independent app.core.data_store),
sharing only Postgres — the same repository/database every replica in a
real deployment would share. No HTTP layer, no Redis, matching
tests/test_pipeline_direct.py's existing direct-pipeline pattern.

Every test below takes the `client` fixture purely to force it to run
first — its actual return value is unused (there's no HTTP call in this
file at all). `client` is what triggers main.py's lifespan, which is
what runs the Alembic migrations that create the transactions/cases
tables in the session's throwaway SQLite DB; without that dependency,
these tests only pass by accident of file-collection order (whichever
other test file happens to use `client` first alphabetically) rather
than reliably on their own — confirmed by running this file in isolation
before adding the dependency, which failed with "no such table: cases".
"""

from app.core.repository import repository
from app.services.orchestrator import run_pipeline
from conftest import make_tx


def _fresh_store() -> dict:
    """A brand-new, empty store — models a freshly-booted API replica
    that has never seen any of this test's data before."""
    return {"transactions": {}, "cases": {}, "graphs": {}}


def test_hop_transaction_on_a_different_replica_joins_the_same_case(client):
    """The crash bug found during the hostile review: a follow-up hop
    explicitly tagged with a case_id another "replica" created used to
    KeyError inside case_manager.py (store["cases"][case_id]) because the
    second replica's local store never heard about that case. Must now
    resolve via Postgres instead of crashing or forking a new case."""
    store_a = _fresh_store()
    origin = make_tx(amount=300000, channel="IMPS", is_cross_border=True)
    result_a = run_pipeline(origin, store_a)
    case_a = result_a["case"]
    assert case_a is not None, "origin transaction should have created a case"
    case_id = case_a["case_id"]

    # Simulate replica A's API layer persisting what it just created —
    # exactly what app/api/transactions.py does after run_pipeline()
    # returns, via repository.save_case()/save_transaction().
    repository.save_transaction(result_a["transaction"])
    repository.save_case(case_a)

    # A second, independent "replica" that has never seen store_a's data,
    # receiving a follow-up hop explicitly tagged with the SAME case_id
    # (exactly how the simulator threads a chain across hops).
    store_b = _fresh_store()
    hop = make_tx(
        sender_account=origin["receiver_account"],
        amount=150000,
        channel="NEFT",
        hop_number=1,
        case_id=case_id,
    )
    result_b = run_pipeline(hop, store_b)  # must not raise KeyError

    assert result_b["case"] is not None
    assert result_b["case"]["case_id"] == case_id, (
        "hop should have joined the existing case via Postgres fallback, "
        f"not created/found a different one ({result_b['case']['case_id']!r})"
    )
    # The fallback should have hydrated the case into store_b's own local
    # cache too, so a THIRD transaction on this same "replica" doesn't
    # need to hit Postgres again.
    assert case_id in store_b["cases"]


def test_fresh_transaction_with_no_case_id_joins_existing_case_from_another_replica(client):
    """The quieter (non-crashing) duplicate-case-creation bug: a brand
    new transaction with NO explicit case_id, whose sender is already the
    origin_account of a case created by a different replica, used to
    silently fork into a second case instead of joining the existing
    chain — because the local-only scan for a matching case never saw
    what the other replica had already created."""
    store_a = _fresh_store()
    origin = make_tx(amount=300000, channel="IMPS", is_cross_border=True)
    result_a = run_pipeline(origin, store_a)
    case_a = result_a["case"]
    assert case_a is not None
    repository.save_transaction(result_a["transaction"])
    repository.save_case(case_a)

    store_b = _fresh_store()
    # A second transaction where the SENDER is the same account that
    # originated the case above, no case_id given — same shape as a
    # legitimate continuation the local-only scan on store_b could never
    # find on its own.
    follow_up = make_tx(
        sender_account=origin["sender_account"],
        receiver_account="ACC-UNRELATED-RECEIVER",
        amount=50000,
        channel="IMPS",
    )
    result_b = run_pipeline(follow_up, store_b)

    assert result_b["case"] is not None
    assert result_b["case"]["case_id"] == case_a["case_id"], (
        "should have joined the case another replica already created for "
        "this sender, not forked a duplicate"
    )


def test_case_lookup_degrades_to_local_only_if_postgres_unavailable(client, monkeypatch):
    """The Postgres fallback itself must degrade gracefully, not raise,
    if Postgres is briefly unreachable during the fallback lookup — a
    flaky fallback must not become a new failure mode. Falls back to "no
    match found", i.e. exactly today's pre-fix (single-replica) behavior,
    rather than crashing the request."""
    from app.core.repository import repository as repo_singleton

    def _broken_get_case(_case_id):
        raise ConnectionError("simulated Postgres outage")

    def _broken_list_cases():
        raise ConnectionError("simulated Postgres outage")

    monkeypatch.setattr(repo_singleton, "get_case", _broken_get_case)
    monkeypatch.setattr(repo_singleton, "list_cases", _broken_list_cases)

    store = _fresh_store()
    tx = make_tx(amount=1500, case_id="CASE-DOES-NOT-EXIST-LOCALLY")
    # Must not raise despite both Postgres fallback paths being broken.
    result = run_pipeline(tx, store)
    assert result["transaction"]["tx_id"] == tx["tx_id"]
