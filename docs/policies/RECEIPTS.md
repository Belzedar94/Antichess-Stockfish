# Receipt policy

Evidence receipts live under `receipts/<EVIDENCE_CLASS>/` and use one of these
classes:

- `D0_DISCOVERY`
- `E1_ENGINEERING`
- `M2_MODEL_SELECTION`
- `S3_STRENGTH`
- `R4_RELEASE`
- `P5_POST_RELEASE`

Each JSON receipt has a same-name `.sha256` sidecar. Receipts and sidecars are
append-only after merge. Corrections are new receipts with
`addendum_to_receipt_id`; history is never rewritten.

CI rejects malformed receipts, missing or incorrect sidecars, tracked NNUE
files, and modifications/deletions of receipts that already exist on the base
branch. A receipt proves only its declared evidence class. In particular:

- canary, loader, loss, crash, or smoke evidence is not Elo;
- Elo does not prove dialect, legal moves, results, labels, assets, or release
  identity;
- a compiler-wrapper timeout is not a compiler failure without process and log
  evidence;
- an isolated HTTP timeout is not an OpenBench outage.
