# Protocol Consumer Compatibility Attestation

Protocol Consumer Compatibility Attestation is a small GenLayer Intelligent Contract for a revision-bound compatibility receipt: a protocol maintainer locks one producer/API change revision against one named consumer constraint revision, then validators independently assess the semantic compatibility of the pair.

## Status

Released and verified. The exact contract source is deployed on GenLayer Studionet at `0xe89ecB9D17F344e314B067521BA2f1cc4DedB428`; the deployed bytes match the local source SHA-256 `225859c6acd29564d8f1dd01644966a880122ee32eddd67bc98d44cf01a21694`. The full live Studionet E2E matrix passed (`7 passed`), and the published package is available at https://github.com/nec465612-create/protocol-consumer-compatibility-attestation.

## Why GenLayer

The contract uses GenLayer only for the part deterministic code cannot establish reliably: semantic interpretation of bounded public evidence. The leader and validators fetch the same digest-pinned sources, evaluate the same rubric and exact-match the fields that affect state. Deterministic code owns identity, bounds, lifecycle, authorization and the `activation_eligible` consequence.

## Workflow

`create_attestation` records the three actors and bounded revision-bound evidence. The owner calls `lock_inputs`. `assess_compatibility` runs one consensus assessment. `COMPATIBLE` is eligible immediately; `CONDITIONAL` remains ineligible until the named consumer acknowledges; `INCOMPATIBLE` and `UNRESOLVED` fail closed. The only downstream surface is the deterministic `read_attestation` view.

## Verification

```text
py -3.13 -m pip install -r requirements.txt
$env:PYTHONIOENCODING="utf-8"
genvm-lint check contracts/protocol_consumer_compatibility_attestation.py
py -3.13 -B -m pytest tests/direct/test_protocol_consumer_compatibility_attestation.py -q -p no:cacheprovider
gltest tests/integration/test_protocol_consumer_compatibility_attestation.py -v -s --network studionet
```

The Studionet command is gated by the exact dual PRE-DEPLOY approval and is not a local test substitute.

## Reuse

Release controllers can read `activation_eligible` from the deterministic view before accepting an upgrade. Protocol maintainers can retain the revision/digest receipt as an audit anchor. Named consumers can acknowledge only a conditional result tied to their address.

## Consensus Engineering Lessons

- Fetch and validate evidence inside the nondeterministic evaluation, but write storage only after consensus.
- Exact-match every decision field that can affect lifecycle or eligibility; explanation text is display-only.
- A digest mismatch, unavailable source, malformed model response or validator disagreement leaves the locked state unchanged.
- An unresolved result can be retried as a new assessment version without changing the locked evidence pair.

## Limitations

This is not a guarantee of runtime compatibility, legal status, security or real-world safety. It is unsuitable where a machine-readable deterministic diff is sufficient, evidence is private or mutable, or no downstream system consumes the fail-closed signal. See `SPECIFICATION.md` for the complete state and binding model.

## Repository structure

```text
contracts/protocol_consumer_compatibility_attestation.py
tests/direct/test_protocol_consumer_compatibility_attestation.py
tests/integration/test_protocol_consumer_compatibility_attestation.py
SPECIFICATION.md
verification/e2e-matrix.md
requirements.txt
```
