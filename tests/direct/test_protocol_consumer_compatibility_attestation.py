import hashlib
import json
import os
from pathlib import Path
import sys

import pytest
from gltest.direct.loader import deploy_contract
from gltest.direct.vm import VMContext


CONTRACT_PATH = Path("contracts/protocol_consumer_compatibility_attestation.py")
OWNER = "0x1111111111111111111111111111111111111111"
CONSUMER = "0x2222222222222222222222222222222222222222"
GATE = "0x3333333333333333333333333333333333333333"
OTHER = "0x4444444444444444444444444444444444444444"
PRODUCER_URL = "https://raw.githubusercontent.com/example/protocol/1111111111111111111111111111111111111111/producer.md"
CONSUMER_URL = "https://raw.githubusercontent.com/example/consumer/2222222222222222222222222222222222222222/constraints.md"
PRODUCER_TEXT = "Protocol v2 changes the retry guidance but retains the response contract."
CONSUMER_TEXT = "The consumer requires the response contract and accepts documented retry changes."


def _reset_state():
    for module in list(sys.modules.values()):
        if hasattr(module, "__known_contract__"):
            module.__known_contract__ = None


@pytest.fixture
def env():
    _reset_state()
    vm = VMContext()
    vm.strict_mocks = True
    vm.check_pickling = True
    vm.sender = OWNER
    deferred = []
    original_unlink = os.unlink

    def tolerant_unlink(path):
        try:
            original_unlink(path)
        except PermissionError:
            deferred.append(path)

    os.unlink = tolerant_unlink
    try:
        contract = deploy_contract(CONTRACT_PATH, vm)
    finally:
        os.unlink = original_unlink
    with vm.activate():
        yield vm, contract
    for path in deferred:
        try:
            original_unlink(path)
        except FileNotFoundError:
            pass


def _sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _create(contract, producer_url=PRODUCER_URL, consumer_url=CONSUMER_URL):
    address_type = sys.modules[contract.__class__.__module__].Address
    return contract.create_attestation(
        address_type(CONSUMER),
        address_type(GATE),
        "protocol-v2",
        producer_url,
        _sha(PRODUCER_TEXT),
        "consumer-v1",
        consumer_url,
        _sha(CONSUMER_TEXT),
        "retry behavior may change if response compatibility remains intact",
        "response shape and error semantics remain required",
    )


def _model(attestation_id=1, verdict="COMPATIBLE", identity=True, breaking=False, action="NONE", reason="ok"):
    return {
        "schema": "PCCA_ASSESSMENT_V1",
        "attestation_id": attestation_id,
        "consumer_identity_match": identity,
        "breaking_change": breaking,
        "required_action": action,
        "verdict": verdict,
        "reason": reason,
        "references": ["producer.md", "constraints.md"],
    }


def _mock(vm, model, producer=PRODUCER_TEXT, consumer=CONSUMER_TEXT):
    vm.mock_web(r".*/producer\.md$", {"status": 200, "body": producer})
    vm.mock_web(r".*/constraints\.md$", {"status": 200, "body": consumer})
    vm.mock_llm(r".*", json.dumps(model))


def _locked(env):
    vm, contract = env
    attestation_id = _create(contract)
    contract.lock_inputs(attestation_id)
    return vm, contract, attestation_id


def test_create_starts_draft_and_read_is_deterministic(env):
    _, contract = env
    attestation_id = _create(contract)
    value = json.loads(contract.read_attestation(attestation_id))
    assert value["lifecycle"] == "DRAFT"
    assert value["assessment_version"] == 0
    assert value["activation_eligible"] is False
    assert value["consumer"] == CONSUMER


def test_lock_is_owner_only_and_immutable(env):
    vm, contract, attestation_id = _locked(env)
    assert json.loads(contract.read_attestation(attestation_id))["lifecycle"] == "LOCKED"
    vm.sender = OTHER
    with pytest.raises(Exception):
        contract.lock_inputs(attestation_id)


@pytest.mark.parametrize("url", [
    "https://example.com/x",
    "https://raw.githubusercontent.com/example/protocol/main/producer.md",
    "https://raw.githubusercontent.com:444/example/protocol/1111111111111111111111111111111111111111/producer.md",
    "https://user@raw.githubusercontent.com/example/protocol/1111111111111111111111111111111111111111/producer.md",
])
def test_evidence_url_requires_immutable_raw_commit(url, env):
    _, contract = env
    with pytest.raises(Exception):
        _create(contract, producer_url=url)
    with pytest.raises(Exception):
        contract.read_attestation(1)


def test_create_rejects_invalid_digest_revision_and_actor_collision(env):
    _, contract = env
    address_type = sys.modules[contract.__class__.__module__].Address
    with pytest.raises(Exception):
        contract.create_attestation(address_type(CONSUMER), address_type(GATE), "", PRODUCER_URL, "0" * 64, "consumer-v1", CONSUMER_URL, _sha(CONSUMER_TEXT), "p", "c")
    with pytest.raises(Exception):
        contract.create_attestation(address_type(CONSUMER), address_type(GATE), "v", PRODUCER_URL, "bad", "consumer-v1", CONSUMER_URL, _sha(CONSUMER_TEXT), "p", "c")
    with pytest.raises(Exception):
        contract.create_attestation(address_type(OWNER), address_type(GATE), "v", PRODUCER_URL, _sha(PRODUCER_TEXT), "consumer-v1", CONSUMER_URL, _sha(CONSUMER_TEXT), "p", "c")
    with pytest.raises(Exception):
        contract.create_attestation(address_type(CONSUMER), address_type(CONSUMER), "v", PRODUCER_URL, _sha(PRODUCER_TEXT), "consumer-v1", CONSUMER_URL, _sha(CONSUMER_TEXT), "p", "c")


@pytest.mark.parametrize("model", [
    {},
    {"schema": "WRONG"},
    _model(verdict="CONDITIONAL", action="NONE"),
    _model(verdict="UNRESOLVED", action="NONE"),
    _model(verdict="COMPATIBLE", identity=False),
    _model(verdict="INCOMPATIBLE", identity=False, breaking=True, action="REMEDIATE"),
    _model(verdict="INCOMPATIBLE", identity=True, breaking=False, action="REMEDIATE"),
])
def test_malformed_or_inconsistent_consensus_output_writes_no_state(model, env):
    vm, contract, attestation_id = _locked(env)
    _mock(vm, model)
    with pytest.raises(Exception):
        contract.assess_compatibility(attestation_id)
    value = json.loads(contract.read_attestation(attestation_id))
    assert value["lifecycle"] == "LOCKED"
    assert value["assessment_version"] == 0


def test_consensus_attestation_id_rejects_bool(env):
    contract = env[1]
    module = sys.modules[contract.__class__.__module__]
    with pytest.raises(Exception):
        module._parse_output(_model(), True)
    with pytest.raises(Exception):
        module._parse_output(_model(attestation_id=True), 1)


@pytest.mark.parametrize("verdict,identity,breaking,action,eligible", [
    ("COMPATIBLE", True, False, "NONE", True),
    ("CONDITIONAL", True, False, "ACKNOWLEDGE", False),
    ("INCOMPATIBLE", True, True, "REMEDIATE", False),
    ("UNRESOLVED", False, False, "UNRESOLVED", False),
])
def test_verdict_drives_deterministic_consequence(verdict, identity, breaking, action, eligible, env):
    vm, contract, attestation_id = _locked(env)
    _mock(vm, _model(verdict=verdict, identity=identity, breaking=breaking, action=action))
    contract.assess_compatibility(attestation_id)
    value = json.loads(contract.read_attestation(attestation_id))
    assert value["lifecycle"] == verdict
    assert value["activation_eligible"] is eligible


def test_conditional_requires_named_consumer_acknowledgement(env):
    vm, contract, attestation_id = _locked(env)
    _mock(vm, _model(verdict="CONDITIONAL", action="ACKNOWLEDGE"))
    contract.assess_compatibility(attestation_id)
    vm.sender = OTHER
    with pytest.raises(Exception):
        contract.acknowledge_condition(attestation_id)
    vm.sender = CONSUMER
    contract.acknowledge_condition(attestation_id)
    value = json.loads(contract.read_attestation(attestation_id))
    assert value["lifecycle"] == "CONDITION_ACKNOWLEDGED"
    assert value["activation_eligible"] is True


def test_unresolved_retry_increments_version_and_preserves_history(env):
    vm, contract, attestation_id = _locked(env)
    _mock(vm, _model(verdict="UNRESOLVED", identity=False, action="UNRESOLVED"))
    contract.assess_compatibility(attestation_id)
    vm.clear_mocks()
    _mock(vm, _model())
    contract.assess_compatibility(attestation_id)
    value = json.loads(contract.read_attestation(attestation_id))
    assert value["assessment_version"] == 2
    assert value["lifecycle"] == "COMPATIBLE"


def test_digest_mismatch_and_external_failure_leave_locked_state(env):
    vm, contract, attestation_id = _locked(env)
    vm.mock_web(r".*/producer\.md$", {"status": 200, "body": "wrong"})
    with pytest.raises(Exception):
        contract.assess_compatibility(attestation_id)
    value = json.loads(contract.read_attestation(attestation_id))
    assert value["lifecycle"] == "LOCKED"
    assert value["assessment_version"] == 0


@pytest.mark.parametrize(
    "leader,validator",
    [
        (_model(), _model(identity=False, verdict="UNRESOLVED", action="UNRESOLVED")),
        (_model(), _model(breaking=True, verdict="INCOMPATIBLE", action="REMEDIATE")),
        (_model(verdict="CONDITIONAL", action="ACKNOWLEDGE"), _model()),
        (_model(), _model(verdict="CONDITIONAL", action="ACKNOWLEDGE")),
    ],
)
def test_each_consequence_field_is_validator_bound(leader, validator, env, monkeypatch):
    import genlayer.gl.vm as gl_vm

    vm, contract, attestation_id = _locked(env)
    _mock(vm, leader)

    def disagree(leader_fn, validator_fn):
        leader_value = leader_fn()
        vm.clear_mocks()
        _mock(vm, validator)
        assert validator_fn(gl_vm.Return(calldata=leader_value)) is False
        raise RuntimeError("validator disagreement")

    monkeypatch.setattr(gl_vm, "run_nondet_unsafe", disagree)
    with pytest.raises(RuntimeError, match="validator disagreement"):
        contract.assess_compatibility(attestation_id)
    assert json.loads(contract.read_attestation(attestation_id))["assessment_version"] == 0


def test_terminal_actions_and_missing_ids_revert(env):
    vm, contract, attestation_id = _locked(env)
    _mock(vm, _model())
    contract.assess_compatibility(attestation_id)
    with pytest.raises(Exception):
        contract.assess_compatibility(attestation_id)
    with pytest.raises(Exception):
        contract.lock_inputs(attestation_id)
    with pytest.raises(Exception):
        contract.read_attestation(99)
