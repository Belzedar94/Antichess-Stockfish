# S3 Fairy-Stockfish panel-input certification v1 preregistration

## Status

**PREREGISTERED. THE CERTIFICATION HARNESS DOES NOT EXIST, NO CERTIFICATION
PROBE HAS RUN, AND NO STRENGTH GAME IS AUTHORIZED.**

This experiment certifies the exact inputs and control plane required before
the owner-requested same-network three-time-control panel. It is engineering
and correctness evidence only. A pass is not Elo, strength, OpenBench,
DATAGEN, model-selection, release, or monitoring evidence.

## Frozen source and comparator boundary

- Rules and service profile: `LICHESS_ANTICHESS_V1` under `AC_REFEREE_V1`.
- Official Stockfish source ancestor:
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`.
- Exact candidate source commit:
  `d08da0c88b7b933eb3c94e6c10a91e0a04f9f769`.
- Exact candidate source tree:
  `31fbae40bd620737a44ee336f8f8596649c027f9`.
- Candidate Windows binary: pending one dual-clean reproducible build from the
  exact candidate source commit. No later source or documentation commit may
  silently replace it.
- Fairy-Stockfish comparator repository:
  `https://github.com/fairy-stockfish/Fairy-Stockfish.git`.
- Comparator commit:
  `6d9d0f5724677dc3aba3c577b0b482b6ec11e44a`.
- Comparator tree:
  `aa4112ea6784cef03fb9b5f87bba632de6168faa`.
- Comparator Windows binary SHA-256:
  `ee0081d77a555ef073e56a04fff604af8d6408a1e2d0afc2e61cea23c11bb902`.
- The remote Fairy-Stockfish `master` head was rechecked on 2026-09-01 and
  still resolved to the frozen comparator commit.

Fairy-Stockfish is an external comparator only. It is neither candidate
ancestry nor a rules authority, and no Fairy-Stockfish implementation may be
copied into the candidate.

## Frozen network and engine options

Both engines must load the same external file bytes:

- bytes: `953248`;
- SHA-256:
  `dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc`;
- license status: unresolved for the exact 2024 artifact;
- distribution: local-only; no copy, embedding, default, release alias, or
  redistribution is permitted.

Candidate options are fixed to:

- `UCI_Variant=antichess`;
- `Antichess_Evaluator=legacy-v1`;
- `Antichess_Search=alpha-beta-v1`;
- `EvalFile=<exact external dd3c path>`;
- `Threads=1`;
- `Hash=512`.

Fairy-Stockfish options are fixed to:

- `UCI_Variant=antichess`;
- `Use NNUE=true`;
- `EvalFile=<the same exact external dd3c path>`;
- `Threads=1`;
- `Hash=512`.

The harness must retain raw UCI transcripts proving every explicit option,
successful readiness, the requested hash capacity, a canonical evaluation or
search response, and the absence of a silent evaluator fallback. Positive and
negative load probes are required for both executables. An engine that silently
uses another network is not certifiable.

## Frozen referee identity

The only local match authority is `AC_REFEREE_V1`:

- Cute Chess base commit:
  `5e84232be4546aaedc9d87a96c91867a1da06ada`;
- patch SHA-256:
  `b8d20a4aa6c4a4a287772cec08b7e952feca88be9120ce11c45a7a3ccfa2a972`;
- derived tree: `639664d19717604326fa5fef21356556db86e27b`;
- profile probe SHA-256:
  `fd45f1f066ce6ff3017a193d5333ccc95e676f9fc795cdd74722abac7564b109`;
- Cute Chess CLI SHA-256:
  `62377837474f166edfae5dcc5801b19bdf0ee28c89ac4bc66832d535be73ae9f`;
- Qt6Core SHA-256:
  `9cf7924077f1ac8758a456e780d9f408c779e76e58680a77ef30ef9807295c43`.

The existing 879-check verifier must pass again. A similarly named unpatched
Cute Chess variant, a changed binary, or a CLI that merely accepts
`-variant antichess` fails certification.

## Frozen external opening-suite candidate

The only book candidate in this experiment is the external local file
`books/antichess.epd` under the owner's Match script directory:

- bytes: `11862`;
- lines: `202`, all non-empty and byte-unique;
- SHA-256:
  `6ec92e4e39a86f8d74504f7556fb27c02fe50fb2cac04951eb5ec01c8f1c2ec2`;
- provenance: not established by the local file;
- license: unresolved;
- distribution: local-only and forbidden from repository or release assets.

Every line must be normalized from four-field EPD to a six-field Antichess FEN
by appending `0 1`. Certification requires all 202 positions to be parseable,
non-terminal, non-automatic-draw, non-duplicate after normalization, and to
have a non-empty legal move set. `AC_REFEREE_V1`, the exact candidate, and the
exact Fairy-Stockfish comparator must expose identical complete legal move
sets. The audit must count mandatory-capture positions and verify that no quiet
move survives whenever a capture exists.

Any single parse, status, legal-set, mandatory-capture, or duplicate failure
rejects the whole book. No line may be deleted after observing a failure; a
different book requires a new preregistration.

## One certification implementation

The planned project-local verifier is
`tools/strength/verify_fsf_panel_inputs_v1.py`. It may use only the Python 3.12
standard library and the exact executables above. Its implementation is
restricted to:

1. checking immutable source, executable, network, book, and runtime hashes;
2. replaying the full `AC_REFEREE_V1` fixture verifier;
3. verifying candidate and Fairy-Stockfish UCI option and network-load
   contracts, including negative load probes;
4. comparing complete legal move sets on every focused fixture and every book
   position;
5. generating a deterministic, result-independent opening schedule;
6. proving a proposed panel launcher rejects malformed or incomplete evidence;
7. executing at most one two-game, color-swapped, non-strength plumbing smoke
   after all prior checks pass; and
8. auditing that smoke's raw log and PGN through `AC_REFEREE_V1`.

The implementation must not change engine or referee source, choose positions
after seeing engine evaluations, tune a time control, run a strength sample,
or import the Atomic runner as an Antichess authority.

## Target panel contract to certify, not execute

The Atomic house methodology is used only for its owner-selected three-rung
and exact-displayed-LOS protocol. The referenced source identities are frozen
in the JSON preregistration. Antichess supplies its own book, referee, runner,
legality, result, and evidence contracts.

| Field | Frozen target |
| --- | --- |
| VSTC | `2000+20` ms |
| STC | `10000+100` ms |
| LTC | `30000+300` ms |
| engines per game | two, each `Threads=1`, `Hash=512` |
| controller count | at most one per TC and at most three total |
| colors | exact two-game pairs from the same opening |
| opening order | SHA-256 ordering from the frozen seed; same schedule for all TCs |
| minimum | total strictly greater than 100 and even in each TC |
| pass | candidate displayed LOS `100.0%` in all three TCs |
| candidate-loss gate | displayed LOS `0.0%` in any TC |
| maximum | 64,000 games per TC |
| adjudication | referee rules only; no score-based draw or resign adjudication |
| recovery | fail closed; no silent resume, deletion, or replay of counted games |

Displayed LOS must be calculated from candidate-perspective W/L/D with the
frozen normal-score formula and rounded once to one decimal. This is an
operational house gate, not mathematical certainty. The final strength
preregistration must freeze the implemented formula, tests, runner hash,
schedule hash, all executable hashes, exact commands, time margin, output
layout, and process lease before the first panel game.

## Certification decision rule

PASS requires all of the following:

- exact input hashes and source ancestry match this preregistration;
- the candidate builds twice from clean state with byte-identical Windows
  binaries under the pinned toolchain and epoch;
- the 879-check referee verification passes;
- both engines pass positive and negative same-network load probes;
- all focused rule fixtures and all 202 book positions have exact three-way
  legal-set agreement;
- the book has no terminal, automatic-draw, empty, or normalized-duplicate
  entry and exercises compulsory capture;
- launcher self-tests reject every frozen malformed-evidence case;
- the single two-game plumbing smoke has color-swapped identical openings,
  exact option mapping, zero illegal moves, crashes, disconnects, stalls, or
  time losses, and a fully passing raw-log/PGN audit;
- official Stockfish remains candidate ancestry and Fairy-Stockfish remains
  outside it; and
- immutable receipts, reproducible build evidence, CI, exact-head review,
  merge, and post-merge CI all pass.

Any mismatch or missing evidence is a fail-closed certification failure. The
strength panel remains unexecuted. Fixing a harness defect may use a new
versioned preregistration; changing or filtering the book, comparator,
network, rules, or pass rule after observing results is prohibited.

## Explicit non-claims

A certification pass admits only a separate, final S3 strength
preregistration. It does not establish that either engine is stronger, does
not authorize OpenBench or DATAGEN, does not promote the legacy network, and
does not authorize a release. Stable publication still requires the owner's
explicit G15 decision.
