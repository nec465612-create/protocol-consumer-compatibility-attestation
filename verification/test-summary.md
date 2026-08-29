# Verification Summary

## Exact published revision

- Published branch: `main`
- Revision root: `9927277c7095541485070a1ce0f0dd63447e68b696b3da7a92b620570a659796`
- Network: GenLayer Studionet, chain ID `61999`
- Contract: `0xe89ecB9D17F344e314B067521BA2f1cc4DedB428`
- Source SHA-256: `225859c6acd29564d8f1dd01644966a880122ee32eddd67bc98d44cf01a21694`

## Checks

- `pytest -q`: `27 passed, 7 skipped`
- `genvm-lint check contracts/protocol_consumer_compatibility_attestation.py --json`: PASS
- `python -m pip check`: PASS
- Studionet integration matrix: `7 passed`
- E2E completion gate: PASS

The exact transaction, consensus, finality, Explorer and authoritative readback evidence is recorded in `verification/e2e-matrix.md`.
