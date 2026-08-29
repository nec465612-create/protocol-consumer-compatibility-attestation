# Protocol Consumer Compatibility Attestation

Protocol Consumer Compatibility Attestation is a small GenLayer Intelligent Contract for a revision-bound compatibility receipt: a protocol maintainer locks one producer/API change revision against one named consumer constraint revision, then validators independently assess the semantic compatibility of the pair.

## Live Deployment

- Network: GenLayer Studionet, Chain ID `61999`
- Contract: [`0xe89ecB9D17F344e314B067521BA2f1cc4DedB428`](https://explorer-studio.genlayer.com/address/0xe89ecB9D17F344e314B067521BA2f1cc4DedB428)
- Deployer: `0x755a55bB1B8A74319De712a846e4055b29780b11`
- Deployment transaction: [`0x15f909ff6a796515d11b7daefa195ba1ec513765b0cd1f8b8baef1c1c1928249`](https://explorer-studio.genlayer.com/tx/0x15f909ff6a796515d11b7daefa195ba1ec513765b0cd1f8b8baef1c1c1928249)
- Published source: [`main`](https://github.com/nec465612-create/protocol-consumer-compatibility-attestation/tree/main)
- Contract source SHA-256: `225859c6acd29564d8f1dd01644966a880122ee32eddd67bc98d44cf01a21694`; deployed source matches byte-for-byte.

The live matrix has seven passing scenarios. A successful consensus example is [`0x2a4146b1527157ce89fefcd8e945712b996f8f5217d0b6f4bb5a38c85c0fb9a3`](https://explorer-studio.genlayer.com/tx/0x2a4146b1527157ce89fefcd8e945712b996f8f5217d0b6f4bb5a38c85c0fb9a3), which stores `COMPATIBLE`. A counterexample is [`0xcae07fbe4a8518379359ee4a20bd7c6d4980e5b41029b695283a2d6c737c1fa5`](https://explorer-studio.genlayer.com/tx/0xcae07fbe4a8518379359ee4a20bd7c6d4980e5b41029b695283a2d6c737c1fa5), which stores `INCOMPATIBLE` and remains ineligible. The complete receipt/readback record is in [`verification/e2e-matrix.md`](verification/e2e-matrix.md).

## Why GenLayer

The contract uses GenLayer only for the part deterministic code cannot establish reliably: semantic interpretation of bounded public evidence. The leader and validators fetch the same digest-pinned sources, evaluate the same rubric and exact-match the fields that affect state. Deterministic code owns identity, bounds, lifecycle, authorization and the `activation_eligible` consequence.

## Workflow

`create_attestation` records the three actors and bounded revision-bound evidence. The owner calls `lock_inputs`. `assess_compatibility` runs one consensus assessment. `COMPATIBLE` is eligible immediately; `CONDITIONAL` remains ineligible until the named consumer acknowledges; `INCOMPATIBLE` and `UNRESOLVED` fail closed. The only downstream surface is the deterministic `read_attestation` view.

## How It Works

The contract stores two commit-pinned raw GitHub evidence references and their SHA-256 digests. Each assessment fetches and validates both sources, gives the same bounded evidence to the leader and validators, requires exact agreement on every consequence-bearing decision field, then stores the accepted result. Explanations are bounded audit context only; `activation_eligible` is derived deterministically from the lifecycle.

## State Model and Invariants

`DRAFT -> LOCKED -> COMPATIBLE | CONDITIONAL | INCOMPATIBLE | UNRESOLVED`. Only the owner can lock inputs. Only the named consumer can acknowledge a `CONDITIONAL` record. Failed consensus, digest mismatch, malformed output, disagreement and invalid transitions leave the prior state unchanged. Only `COMPATIBLE` or `CONDITION_ACKNOWLEDGED` is eligible.

## Public API

- `create_attestation(...)`: create a bounded attestation for one producer/consumer pair.
- `lock_inputs(attestation_id)`: freeze the evidence and revisions.
- `assess_compatibility(attestation_id)`: run the consensus assessment.
- `acknowledge_condition(attestation_id)`: named-consumer acknowledgement.
- `read_attestation(attestation_id)`: deterministic oracle view for release controllers and downstream gates.

## Consensus Binding Matrix

| field | source | stored? | downstream effect | validator check | binding mode | differential test |
|---|---|---:|---|---|---|---|
| evidence digests | caller input + fetch | yes | rejects stale evidence | both nodes verify SHA-256 | exact digest | digest mismatch regression |
| consumer identity match | consensus output | yes | prevents cross-consumer approval | exact leader/validator match | exact boolean | altered consequence output rejection |
| breaking change | consensus output | yes | drives incompatibility | exact leader/validator match | exact boolean | altered consequence output rejection |
| required action | consensus output | yes | controls acknowledgement | exact match plus invariant | exact enum | altered consequence output rejection |
| verdict | consensus output | yes | lifecycle and eligibility | exact match plus cross-field invariant | exact enum | verdict consequence regression |
| reason/references | consensus output | yes | display-only audit context | bounded/schema checked | non-authoritative | malformed output regression |
| activation eligible | deterministic derivation | yes | downstream release gate | derived after accepted consensus | deterministic | compatible/conditional/incompatible regressions |

## Security and Failure Boundaries

Fetched evidence and submitted excerpts are untrusted data delimited from instructions. URLs must be HTTPS raw GitHub files pinned to full commit SHAs. Bounds, UTF-8 validation, digest checks, actor separation, lifecycle checks and fail-closed state writes are deterministic. GenLayer is not needed when a compatibility rule can be decided by a deterministic schema or diff.

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

## Test Results

The published verification record reports `27 passed, 7 skipped` for local tests, GenVM lint/validation PASS, pip check PASS, and `7 passed` for the full Studionet E2E matrix. Reproduction commands are listed above; the exact live receipts and readbacks are in [`verification/e2e-matrix.md`](verification/e2e-matrix.md), and the input fixtures are in [`samples/studionet-inputs.json`](samples/studionet-inputs.json).

## Reusable Integrations

- A release controller can gate an upgrade on `read_attestation(...).activation_eligible`.
- A protocol maintainer can retain the locked revision/digest pair as an audit anchor.
- A named consumer can acknowledge only its own conditional compatibility obligation.

## Repository structure

```text
contracts/protocol_consumer_compatibility_attestation.py
tests/direct/test_protocol_consumer_compatibility_attestation.py
tests/integration/test_protocol_consumer_compatibility_attestation.py
samples/studionet-inputs.json
SPECIFICATION.md
verification/e2e-matrix.md
verification/test-summary.md
requirements.txt
LICENSE
.gitignore
```

## License

MIT; see [`LICENSE`](LICENSE).
