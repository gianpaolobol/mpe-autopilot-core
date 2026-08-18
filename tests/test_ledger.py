import pytest

from autopilot_core.ledger import HashChainLedger, LedgerIntegrityError


def test_hash_chain_verifies_and_detects_tampering():
    ledger = HashChainLedger()
    ledger.append(
        "RUN_STARTED",
        tick_id="tick-1",
        run_id="run-1",
        runner_id="primary",
        controller_sha="a" * 40,
    )
    ledger.append(
        "NEXT_TASK",
        tick_id="tick-1",
        run_id="run-1",
        runner_id="primary",
        controller_sha="a" * 40,
        payload={"task": "generic-probe"},
    )
    ledger.verify()

    tampered = [dict(event) for event in ledger.events]
    tampered[0]["payload"] = {"task": "changed"}
    with pytest.raises(LedgerIntegrityError):
        HashChainLedger(tampered).verify()


def test_ledger_sanitizes_payload_before_hashing():
    ledger = HashChainLedger()
    event = ledger.append(
        "EVENT",
        tick_id="tick",
        run_id="run",
        runner_id="runner",
        controller_sha="b" * 40,
        payload={"password": "should-not-persist"},
    )
    assert event["payload"]["password"] == "***"
    ledger.verify()
