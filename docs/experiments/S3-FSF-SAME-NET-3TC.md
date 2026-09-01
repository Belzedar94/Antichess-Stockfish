# S3 Fairy-Stockfish same-network three-time-control panel

## Status

**PREREGISTERED; RUNNER NOT IMPLEMENTED; NO STRENGTH GAME AUTHORIZED OR RUN.**

The exact engine capabilities and panel inputs are closed. This document now
freezes the final experiment design before implementation of the project-local
runner. A separate immutable authorization containing the reviewed runner
hash, test hash, merge identity, post-merge CI, output root, and active host
lease is still mandatory before the first strength game.

The objective is a whole-engine comparison between the specialized
Antichess-Stockfish candidate and the current Fairy-Stockfish master, with the
same legacy network bytes loaded by both engines. The result cannot isolate
NNUE quality.

## Frozen competitors and inputs

| Input | Frozen identity |
| --- | --- |
| official Stockfish ancestor | `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6` |
| Antichess-Stockfish source | `d08da0c88b7b933eb3c94e6c10a91e0a04f9f769`, tree `31fbae40bd620737a44ee336f8f8596649c027f9` |
| Antichess-Stockfish Windows binary | `5459225015a9734a3f0322b3fa4a9accdb74c5d3cb82a4efe371ae5715286213` |
| Fairy-Stockfish source | `6d9d0f5724677dc3aba3c577b0b482b6ec11e44a`, tree `aa4112ea6784cef03fb9b5f87bba632de6168faa` |
| Fairy-Stockfish Windows binary | `ee0081d77a555ef073e56a04fff604af8d6408a1e2d0afc2e61cea23c11bb902` |
| shared network | `dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc`, 953,248 bytes |
| opening suite | `6ec92e4e39a86f8d74504f7556fb27c02fe50fb2cac04951eb5ec01c8f1c2ec2`, 202 EPD positions |
| schedule identity | `62f5efe976a690412daa03703ad31041804b1a67d715fc1c81a5606dca9cc4db` |
| schedule evidence file | `3d2af0c2af00ec6df8e3250aff1a46f349c40ffc642dbbb40b8ddd3c1b9ea55e` |
| referee CLI | `AC_REFEREE_V1`, `62377837474f166edfae5dcc5801b19bdf0ee28c89ac4bc66832d535be73ae9f` |
| referee probe | `fd45f1f066ce6ff3017a193d5333ccc95e676f9fc795cdd74722abac7564b109` |

Fairy-Stockfish master was rechecked at preregistration and still resolved to
the frozen commit. Fairy-Stockfish is a comparator only; it is not candidate
ancestry or a rules authority. The shared network and opening suite are
external local-only inputs with unresolved redistribution licenses. They must
not be copied into the repository or any release.

Candidate options are exactly `UCI_Variant=antichess`,
`Antichess_Evaluator=legacy-v1`, `Antichess_Search=alpha-beta-v1`, the exact
network path, `Threads=1`, and `Hash=512`. Comparator options are exactly
`UCI_Variant=antichess`, `Use NNUE=true`, the same canonical network path,
`Threads=1`, and `Hash=512`. No additional engine option is permitted, and
both engines restart for every game.

## Closed input certification

The v2 certification passed once. It proved exact three-way legal-move-set
agreement among both engines and `AC_REFEREE_V1` on all 56 focused positions
and all 202 book positions, including compulsory-capture coverage. It also
passed positive and negative network probes, all 879 referee checks, and a
two-game forced-terminal plumbing smoke. That smoke is not strength evidence.

The PASS receipt is
`74ae97afa1738f15a68339c6e646ffc1b25ebdac955c6615c3b3ae36d9b5bc5e`.
Its result file is
`5a5a9600cd2ae455c0daefce7b91c12fb73d4280c57e7d195c235551eba01ae5`.
The post-merge closure is
`086ac580c322458f297741e643fa1fc107f7951703775a2ff26d5f8bd09472f5`.

## Atomic methodology boundary

Only the owner-selected statistical and stopping protocol is inherited from
Atomic. Its pinned methodology commit is
`70ea2218cec918ddb393055b8929d4df7e0d9711`. Antichess does not inherit the
Atomic variant, runner, worker count, engines, network, book, config, referee,
options, adjudication, artifacts, or results.

The Antichess panel runs one controller at a time with concurrency one. This is
stricter than Atomic's worker count and makes every observation boundary an
actual completed color-swapped pair.

| Field | Frozen value |
| --- | --- |
| TC order | VSTC, then STC, then LTC |
| VSTC | `2000+20` ms |
| STC | `10000+100` ms |
| LTC | `30000+300` ms |
| games per block | two, same opening, colors swapped |
| minimum | `Total > 100`; first eligible total is 102 |
| pass per TC | candidate displayed LOS exactly `100.0%` |
| candidate-loss gate | displayed LOS exactly `0.0%` |
| maximum | 64,000 games per TC |
| overall pass | all three independent TCs pass |
| formula | candidate W/L/D, frozen legacy normal-score formula, one `%.1f` formatting step |
| zero variance/domain failure | LOS unavailable; never PASS |
| SPRT | prohibited |

The gate is evaluated only after a fully audited pair. A TC starts only after
the preceding TC passes. A `0.0%` candidate-loss gate or a 64,000-game miss
rejects the campaign and later TCs do not run. No result-aware extension,
repetition, retuning, threshold change, or optional stopping is allowed.

## Opening schedule

The schedule is the ascending order of
`sha256(seed + LF + one-based source index + LF + normalized FEN)` using seed
`ANTICHESS_S3_FSF_SAME_NET_3TC_V1`. Pair `p` uses schedule entry
`((p - 1) modulo 202) + 1`. Every TC starts again at pair one and uses this
same order. The book cannot be filtered, substituted, or reordered after any
result.

The schedule is reconstructed from the external book and must match the
certified identity above. Its FEN content remains local evidence because the
book is not redistributable.

## Planned runner and evidence

The planned Windows-only standard-library runner is
`tools/strength/run_fsf_same_net_3tc_v1.py`, with tests at
`tests/antichess/test_s3_strength_runner_v1.py`. It will launch the exact
patched Cute Chess referee once per pair, at concurrency one, with a 200 ms
time margin and a 900-second no-completed-pair watchdog. It may terminate only
its own newly created controller and engine descendants, with a bounded
30-second shutdown.

Each pair directory must contain its exact opening, launch record, raw UCI log,
PGN, and referee audit. Each TC must contain an append-only pair ledger, WLD,
pentanomial, Elo, confidence interval, LOS, defect counts, and terminal result.
The campaign must also contain preflight and postflight fingerprints, aggregate
result, and lease closure. Output roots are create-once and cannot be
overwritten.

Every PGN move is replayed through `AC_REFEREE_V1`; the final position and
winner must agree with the PGN. There is no score-based draw or resign
adjudication and no tablebase use.

## Fail-closed invalidation and recovery

Any input drift, load fallback, option/profile mismatch, opening or color
drift, illegal move, referee-result disagreement, time loss, crash,
disconnect, stall, controller error, or missing raw/audited evidence invalidates
the entire current TC. A partial pair is never counted.

There is no silent resume, replay, deletion, replacement, or automatic rerun
under this experiment identity. Evidence is preserved, the incident is
diagnosed, and any full TC restart from pair one requires a new immutable
authorization.

## Remaining admission gate

This preregistration freezes method and inputs only. Before the first strength
game, the runner and tests must be implemented without changing this contract,
frozen by SHA-256, pass local correctness checks, receive exact-head review,
merge, and pass post-merge CI. A final immutable authorization must then bind
those identities to a new output root and an active exclusive host lease after
two clean resource snapshots.

Until all of those conditions hold, no VSTC, STC, LTC, WLD, pentanomial, Elo,
LOS, OpenBench, DATAGEN, model-selection, release, or monitoring claim is
authorized. Stable publication remains subject to an explicit owner G15
decision after a complete verified draft.
