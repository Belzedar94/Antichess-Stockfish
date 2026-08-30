# Gate index

Allowed terminal states are `GO_NEXT_PHASE`, `BLOCKED_DISCOVERY`,
`NO_VALID_BASELINE`, `REJECTED_ENGINEERING`, `REJECTED_MODEL`,
`REJECTED_STRENGTH`, `REJECTED_RELEASE`, and `RELEASED_MONITORED`.

Current project state: **`GO_NEXT_PHASE`**.

This file is a human-readable index. Committed receipts are authoritative and
append-only; a gate transition requires a new receipt or addendum.

| Gate | Scope | Status | Closure evidence |
| --- | --- | --- | --- |
| P0 | Root, owner source-base decision, repository, worktrees, remotes, namespaces, resource boundaries | PASS | Official pin, clean branch transition, rejected-line archive, D0 receipt |
| P1 | Primary research and authority dossier | PASS | Pinned Lichess/scalachess/lila sources, independent chessops pin, negative profiles |
| P2 | Executable dialect, source architecture, reference, referee, evaluator, distribution | PASS | Frozen primary contract, patched `AC_REFEREE_V1`, exact legacy compatibility, and a fail-closed no-redistribution boundary for the unresolved 2024 network license |
| P3 | Candidate clean reproducible build and UCI surface | PASS | Merge `d08cc316`: two clean Windows builds are byte-identical, Linux post-merge CI is reproducible, and the Antichess bench repeats exactly |
| P4 | Differential legal/result/notation correctness | PASS | The claim-at-horizon defect is fixed and frozen; exact candidate, legacy network, `AC_REFEREE_V1`, raw log, and 100-ply PGN audit pass |
| P5 | Evaluator and legacy-network boundary | PASS | Scalar full-refresh parity covers 58 exact values and all material buckets; loader passes 82 checks including claim-at-horizon and remains fail-closed |
| P6 | Sanitizers, deterministic digest, CI, baseline manifest/tag | PASS | PR #3 and its post-merge CI certify the corrected engine; PR #4 and exact-head post-merge run `33310697041` close the recertification governance record; manifest V2 and immutable tag `baseline/lichess-antichess-v1-d08cc316` remain verified |
| P7 | Search-hypothesis readiness | IN_PROGRESS | `p7-alpha-beta-v1-r2` freezes one plain alpha-beta hypothesis, exact comparator, 13-case fixed-work corpus, direct UCI harness, thresholds, and stop rule; the one-shot exhaustive comparator record is frozen as `5d3b14bd...b1c16b`, and the isolated candidate implementation is not yet built or compared |
| P8 | Antichess DATAGEN schema and labels | BLOCKED_BY_P7 | Own magic/schema, physical records, golden perspective labels |
| P9 | Producer/consumer handshake and G0 | BLOCKED_BY_P8 | Exact counts, framing, legality, results, recovery, quarantine |
| P10 | Official public-build DATAGEN canary | BLOCKED_BY_P9 | Production path proves the exact versioned dialect contract |
| P11 | Leased scale and split audit | BLOCKED_BY_P10 | Unique chunks, exact totals, trajectory-level split evidence |
| P12 | NNUE V2 state/content/topology contract | BLOCKED_BY_P11 | Decoder/scalar parity and fail-closed quantized container |
| P13 | Training reproducibility and local model selection | BLOCKED_BY_P12 | Frozen split, multiple seeds, fixed-work, exact resume |
| P14 | STC/LTC strength and winner ancestry | BLOCKED_BY_P13 | Preregistered official science, no optional stopping |
| P15 | Release draft and owner G15 | BLOCKED_BY_P14 | Dual clean builds, SBOM, licenses, assets reverified |
| P16 | Publication and post-release monitoring | BLOCKED_BY_P15 | Immutable stable tag plus rollback and monitoring receipts |

## Current stop conditions

- P7 permits only one preregistered search hypothesis at a time. No timing,
  strength, book, Elo, or campaign run may start without an exact comparator,
  referee/runner, workload, stopping rule, and exclusive host lease.
- `p7-alpha-beta-v1-r2` executed its comparator phase exactly once under an
  exclusive host lease. Candidate implementation may now begin only in a
  separate commit; the candidate comparison remains one-shot after a clean,
  hash-frozen build.
- No DATAGEN or NNUE V2 work may begin before its preceding gates pass.
- No official OpenBench Antichess work before a versioned client/server/referee
  mapping passes the same differential fixtures in the production path.
- No redistribution or release alias for the legacy network while its license
  and exact compatibility remain unresolved.
- Local ASan/UBSan runtimes remain unavailable. The exact-head Linux CI pass is
  the P6 sanitizer evidence and must not be generalized to untested targets.
- No Fairy-Stockfish implementation commit or file may enter candidate
  ancestry.
