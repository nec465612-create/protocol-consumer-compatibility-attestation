# Protocol Consumer Compatibility Attestation

## Purpose

This contract creates a revision-bound receipt for one producer protocol/API change and one named consumer constraint. It is a fail-closed release signal, not a general truth oracle.

## Lifecycle and roles

The submitting owner is the protocol maintainer. The record names exactly one consumer and one downstream release gate. `DRAFT` records become immutable `LOCKED` records through `lock_inputs`.

`LOCKED` is assessed by one consensus execution and becomes exactly one of `COMPATIBLE`, `CONDITIONAL`, `INCOMPATIBLE`, or `UNRESOLVED`. Only the named consumer can move `CONDITIONAL` to `CONDITION_ACKNOWLEDGED`. A failed or unresolved assessment can be retried as the next `assessment_version` over the same locked inputs.

## Evidence boundary

Both evidence URLs must be HTTPS raw GitHub file URLs pinned to a full commit SHA. The contract stores the expected SHA-256 digest, revision labels and bounded submitted excerpts. Runtime fetches are bounded, strict UTF-8 and digest checked. Evidence is untrusted data and cannot issue prompt instructions.

## Consensus and state binding

The leader fetches both pinned sources and returns a strict schema containing `consumer_identity_match`, `breaking_change`, `required_action`, `verdict`, plus display-only explanation fields. Validators independently fetch and evaluate the same evidence and exact-match every decision field. Storage changes happen only after accepted consensus. `activation_eligible` is derived deterministically: only `COMPATIBLE` or acknowledged `CONDITIONAL` is true.

## Public API

- `create_attestation(...) -> u64`
- `lock_inputs(attestation_id) -> None`
- `assess_compatibility(attestation_id) -> None`
- `acknowledge_condition(attestation_id) -> None`
- `read_attestation(attestation_id) -> str`

## Consensus Binding Matrix

| field | source | stored? | downstream effect | validator check | binding mode | differential test |
|---|---|---:|---|---|---|---|
| producer/consumer revisions | caller input | yes | identifies the assessed revision pair | frozen into both prompts | immutable input | `test_create_starts_draft_and_read_is_deterministic` |
| producer/consumer evidence digests | caller input + runtime fetch | yes | rejects stale or changed evidence | both nodes verify SHA-256 | exact digest | `test_digest_mismatch_and_external_failure_leave_locked_state` |
| consumer identity match | consensus output | yes | prevents compatibility approval for another relationship | exact leader/validator match | exact boolean | `test_each_consequence_field_is_validator_bound` |
| breaking change | consensus output | yes | drives `INCOMPATIBLE` and ineligibility | exact leader/validator match | exact boolean | `test_each_consequence_field_is_validator_bound` |
| required action | consensus output | yes | controls conditional acknowledgement | exact leader/validator match and invariant | exact enum | `test_each_consequence_field_is_validator_bound` |
| verdict | consensus output | yes | lifecycle and gate | exact leader/validator match and cross-field invariant | exact enum | `test_verdict_drives_deterministic_consequence` |
| reason/references | consensus output | yes | display-only audit context | bounded and schema-checked; never controls state | non-authoritative | `test_malformed_or_inconsistent_consensus_output_writes_no_state` |
| activation_eligible | deterministic derivation | yes | downstream fail-closed release gate | not caller/model-controlled; derived after consensus | deterministic | `test_verdict_drives_deterministic_consequence` and `test_conditional_requires_named_consumer_acknowledgement` |

## Limitations

This receipt does not prove runtime behavior, legal compliance or safety. It depends on availability and stability of pinned public evidence and validator model execution. Ambiguous evidence, digest failure, malformed output or validator disagreement must not approve a record. If compatibility is fully machine-readable, a deterministic CI/schema check is simpler.
