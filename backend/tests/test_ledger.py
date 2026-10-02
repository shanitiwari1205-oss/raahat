import os

import pytest

from app.ledger.store import GENESIS_HASH, Ledger


@pytest.fixture
def ledger(tmp_path):
    db_path = str(tmp_path / "test_ledger.db")
    l = Ledger(db_path=db_path)
    yield l
    l.close()


def test_append_chains_hashes(ledger):
    r1 = ledger.append(
        stakeholder_type="donor_to_depot", from_stakeholder="donor-1", to_stakeholder="depot-1",
        resource=None, units=0, fund_amount=150000, description="initial fund",
    )
    assert r1.prev_hash == GENESIS_HASH

    r2 = ledger.append(
        stakeholder_type="depot_to_zone", from_stakeholder="depot-1", to_stakeholder="zone-1",
        resource="water", units=50, fund_amount=1000, description="relief delivery",
    )
    assert r2.prev_hash == r1.hash
    assert r2.hash != r1.hash


def test_verify_passes_on_untampered_chain(ledger):
    for i in range(5):
        ledger.append(
            stakeholder_type="depot_to_zone", from_stakeholder="depot-1", to_stakeholder=f"zone-{i}",
            resource="water", units=10, fund_amount=200, description="delivery",
        )
    result = ledger.verify()
    assert result["valid"] is True
    assert result["records_checked"] == 5
    assert result["break_at_id"] is None


def test_verify_detects_tampering(ledger):
    for i in range(5):
        ledger.append(
            stakeholder_type="depot_to_zone", from_stakeholder="depot-1", to_stakeholder=f"zone-{i}",
            resource="water", units=10, fund_amount=200, description="delivery",
        )
    # tamper with the 3rd record directly, bypassing append() -- proves the
    # tamper-evidence claim is real, not decorative
    ledger._debug_corrupt_record(record_id=3, new_units=99999)

    result = ledger.verify()
    assert result["valid"] is False
    assert result["break_at_id"] == 3


def test_fund_and_resource_fields_both_present(ledger):
    r = ledger.append(
        stakeholder_type="depot_to_zone", from_stakeholder="depot-1", to_stakeholder="zone-1",
        resource="medicine", units=20, fund_amount=3000, description="delivery",
    )
    assert r.data["resource"] == "medicine"
    assert r.data["units"] == 20
    assert r.data["fund_amount"] == 3000
    assert r.data["stakeholder_type"] == "depot_to_zone"


def test_list_records_paginated(ledger):
    for i in range(10):
        ledger.append(
            stakeholder_type="depot_to_zone", from_stakeholder="depot-1", to_stakeholder=f"zone-{i}",
            resource="water", units=1, fund_amount=20, description="x",
        )
    page1 = ledger.list_records(limit=5, offset=0)
    page2 = ledger.list_records(limit=5, offset=5)
    assert len(page1) == 5
    assert len(page2) == 5
    assert page1[0].id != page2[0].id
