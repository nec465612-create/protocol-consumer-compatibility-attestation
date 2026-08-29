import os
import json
from pathlib import Path

import pytest
from gltest import get_accounts, get_contract_factory, get_default_account
from gltest.assertions import tx_execution_succeeded
from gltest.types import TransactionStatus
from gltest.utils import extract_contract_address


pytestmark = pytest.mark.skipif(
    os.getenv("PCCA_RUN_STUDIONET") != "1",
    reason="set PCCA_RUN_STUDIONET=1 only after dual PRE-DEPLOY approval",
)

CONTRACT = Path(__file__).parents[2] / "contracts" / "protocol_consumer_compatibility_attestation.py"
PRODUCER_URL = "https://raw.githubusercontent.com/octocat/Hello-World/762941318ee16e59dabbacb1b4049eec22f0d303/README"
PRODUCER_TEXT = "Hello World!\n"
PRODUCER_SHA256 = "03ba204e50d126e4674c005e04d82e84c21366780af1f43bd54a37816b6ab340"
CONSUMER_URL = "https://raw.githubusercontent.com/octocat/Spoon-Knife/d0dd1f61b33d64e29d8bc1372a94ef6a2fee76a9/README.md"
CONSUMER_SHA256 = "f93aba3ff091ee0b498ae165ff08453620f9802fc6098662e0b9ce57b7273e6d"


def _assert_success(label, receipt):
    tx_hash = receipt.get("tx_id") or receipt.get("hash")
    assert receipt.get("status_name") == "FINALIZED", f"{label}: {receipt}"
    assert receipt.get("result_name") == "MAJORITY_AGREE", f"{label}: {receipt}"
    assert tx_execution_succeeded(receipt), f"{label}: {receipt}"
    assert isinstance(tx_hash, str) and tx_hash.startswith("0x")
    print("PCCA_TX_EVIDENCE=" + json.dumps({"label": label, "tx_id": tx_hash}, sort_keys=True))
    return tx_hash


def _assess_with_one_disagreement_retry(contract, record_id, label):
    for attempt in range(2):
        receipt = contract.assess_compatibility(args=[record_id]).transact(
            wait_transaction_status=TransactionStatus.FINALIZED
        )
        if tx_execution_succeeded(receipt):
            return _assert_success(label, receipt)
        tx_hash = receipt.get("tx_id") or receipt.get("hash")
        if (
            attempt == 0
            and receipt.get("status_name") == "FINALIZED"
            and receipt.get("result_name") == "MAJORITY_DISAGREE"
        ):
            print(
                "PCCA_TX_EVIDENCE="
                + json.dumps(
                    {"label": label + "-disagreement", "tx_id": tx_hash},
                    sort_keys=True,
                )
            )
            continue
        assert False, f"{label}: {receipt}"
    raise AssertionError(f"{label}: bounded disagreement retry exhausted")


@pytest.fixture(scope="session")
def live():
    account = get_default_account()
    consumer_account = get_accounts()[1]
    factory = get_contract_factory(contract_file_path=CONTRACT)
    deploy_receipt = factory.deploy_contract_tx(
        args=[], account=account, wait_transaction_status=TransactionStatus.FINALIZED
    )
    _assert_success("deploy", deploy_receipt)
    address = extract_contract_address(deploy_receipt)
    return {
        "contract": factory.build_contract(contract_address=address, account=account),
        "factory": factory,
        "consumer_account": consumer_account,
        "next_id": 1,
    }


def _create_and_lock(
    live,
    producer_digest=PRODUCER_SHA256,
    producer_excerpt="A named consumer constraint applies to this protocol revision.",
    consumer_excerpt="The consumer requires compatibility with the protocol behavior.",
    consumer=None,
):
    contract = live["contract"]
    record_id = live["next_id"]
    live["next_id"] += 1
    consumer = consumer or "0x2222222222222222222222222222222222222222"
    gate = "0x3333333333333333333333333333333333333333"
    create_receipt = contract.create_attestation(
        args=[
            consumer,
            gate,
            "protocol-v2",
            PRODUCER_URL,
            producer_digest,
            "consumer-v1",
            CONSUMER_URL,
            CONSUMER_SHA256,
            producer_excerpt,
            consumer_excerpt,
        ]
    ).transact(wait_transaction_status=TransactionStatus.FINALIZED)
    _assert_success("create", create_receipt)
    lock_receipt = contract.lock_inputs(args=[record_id]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    _assert_success("lock", lock_receipt)
    return record_id


def test_studionet_create_lock_and_authoritative_readback(live):
    record_id = _create_and_lock(live)
    contract = live["contract"]
    locked = json.loads(contract.read_attestation(args=[record_id]).call())
    assert locked["lifecycle"] == "LOCKED"
    assert locked["assessment_version"] == 0
    assert locked["activation_eligible"] is False


def test_studionet_consensus_assessment_and_decision_readback(live):
    record_id = _create_and_lock(
        live,
        producer_excerpt=(
            "Protocol-v2 keeps the same endpoint, response fields, error semantics, "
            "and consumer-visible behavior. This is a non-breaking compatibility change."
        ),
        consumer_excerpt=(
            "Consumer-v1 requires the existing endpoint, response fields, error semantics, "
            "and behavior; no additional acknowledgement is required."
        ),
    )
    contract = live["contract"]
    _assess_with_one_disagreement_retry(contract, record_id, "assess")
    assessed = json.loads(contract.read_attestation(args=[record_id]).call())
    assert assessed["assessment_version"] == 1
    assert assessed["lifecycle"] == "COMPATIBLE"
    assert assessed["activation_eligible"] is True


def test_studionet_conditional_assessment_and_named_acknowledgement(live):
    consumer = live["consumer_account"].address
    record_id = _create_and_lock(
        live,
        producer_excerpt=(
            "Protocol-v2 adds an optional response field while preserving all required "
            "consumer behavior. The named consumer must acknowledge the documented optional field."
        ),
        consumer_excerpt=(
            "Consumer-v1 accepts additive optional response fields only after named acknowledgement; "
            "all required fields and semantics remain unchanged."
        ),
        consumer=consumer,
    )
    owner_contract = live["contract"]
    _assess_with_one_disagreement_retry(owner_contract, record_id, "assess-conditional")
    assessed = json.loads(owner_contract.read_attestation(args=[record_id]).call())
    assert assessed["lifecycle"] == "CONDITIONAL"
    assert assessed["required_action"] == "ACKNOWLEDGE"
    assert assessed["activation_eligible"] is False
    consumer_contract = live["factory"].build_contract(
        contract_address=owner_contract.address,
        account=live["consumer_account"],
    )
    acknowledge_receipt = consumer_contract.acknowledge_condition(
        args=[record_id]
    ).transact(wait_transaction_status=TransactionStatus.FINALIZED)
    _assert_success("acknowledge-condition", acknowledge_receipt)
    acknowledged = json.loads(owner_contract.read_attestation(args=[record_id]).call())
    assert acknowledged["lifecycle"] == "CONDITION_ACKNOWLEDGED"
    assert acknowledged["activation_eligible"] is True


def test_studionet_incompatible_counterexample_is_ineligible(live):
    record_id = _create_and_lock(
        live,
        producer_excerpt=(
            "For consumer-v1, protocol-v2 omits the mandatory response field `account_id` "
            "from every response. The consumer-v1 response schema requires that field, so "
            "this is an explicit breaking change and remediation is required."
        ),
        consumer_excerpt=(
            "Consumer-v1 requires `account_id` in every response. Any protocol-v2 response "
            "without `account_id` is incompatible, is a breaking change, and requires "
            "remediation."
        ),
    )
    contract = live["contract"]
    _assess_with_one_disagreement_retry(contract, record_id, "assess-incompatible")
    assessed = json.loads(contract.read_attestation(args=[record_id]).call())
    assert assessed["lifecycle"] == "INCOMPATIBLE"
    assert assessed["breaking_change"] is True
    assert assessed["required_action"] == "REMEDIATE"
    assert assessed["activation_eligible"] is False


def test_studionet_digest_failure_is_fail_closed(live):
    record_id = _create_and_lock(live, producer_digest="0" * 64)
    contract = live["contract"]
    negative = contract.assess_compatibility(args=[record_id]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    print("PCCA_TX_EVIDENCE=" + json.dumps({"label": "digest-failure", "tx_id": negative.get("tx_id") or negative.get("hash")}, sort_keys=True))
    assert negative.get("status_name") == "FINALIZED"
    assert negative.get("result_name") in {"MAJORITY_AGREE", "MAJORITY_DISAGREE"}
    assert not tx_execution_succeeded(negative)
    unchanged = json.loads(contract.read_attestation(args=[record_id]).call())
    assert unchanged["lifecycle"] == "LOCKED"
    assert unchanged["assessment_version"] == 0


def test_studionet_invalid_terminal_transition_is_fail_closed(live):
    record_id = _create_and_lock(live)
    contract = live["contract"]
    assess_receipt = contract.assess_compatibility(args=[record_id]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    _assert_success("assess-before-replay", assess_receipt)
    before = json.loads(contract.read_attestation(args=[record_id]).call())
    replay = contract.assess_compatibility(args=[record_id]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    assert replay.get("status_name") == "FINALIZED"
    assert replay.get("result_name") == "MAJORITY_AGREE"
    after = json.loads(contract.read_attestation(args=[record_id]).call())
    if before["lifecycle"] == "UNRESOLVED":
        assert tx_execution_succeeded(replay)
        assert after["assessment_version"] == before["assessment_version"] + 1
    else:
        assert not tx_execution_succeeded(replay)
        assert after == before


def test_studionet_owner_cannot_acknowledge_as_named_consumer(live):
    record_id = _create_and_lock(live)
    contract = live["contract"]
    negative = contract.acknowledge_condition(args=[record_id]).transact(
        wait_transaction_status=TransactionStatus.FINALIZED
    )
    assert negative.get("status_name") == "FINALIZED"
    assert negative.get("result_name") == "MAJORITY_AGREE"
    assert not tx_execution_succeeded(negative)
    unchanged = json.loads(contract.read_attestation(args=[record_id]).call())
    assert unchanged["lifecycle"] == "LOCKED"
    assert unchanged["activation_eligible"] is False
