# ADR-AC-002: Legacy Antichess network compatibility

- Status: accepted for local compatibility testing; not accepted for
  redistribution or default promotion
- Date: 2026-08-29
- Rules profile: `LICHESS_ANTICHESS_V1`
- Source base: official Stockfish development commit
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`

## Decision

Antichess-Stockfish implements an independent, scalar, full-refresh reader and
evaluator for the exact legacy network identified below. The implementation is
part of the official-Stockfish-derived candidate and does not import
Fairy-Stockfish source. A pinned Fairy-Stockfish executable is used only as an
evaluation-format oracle.

The legacy backend is opt-in through `Antichess_Evaluator=legacy-v1` and an
external `EvalFile`. The default remains `engineering-neutral` while the
project has `NO_VALID_BASELINE`. Selecting `legacy-v1` without a successfully
loaded compatible file refuses search. Any failed reload clears the previously
loaded network.

The network bytes are not committed, embedded, renamed, redistributed, or
eligible for a release alias. Those actions require an explicit redistribution
license and a later release gate.

## Exact network identity

- Filename: `antichess-dd3cbe53cd4e.nnue`
- Bytes: `953,248`
- SHA-256:
  `dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc`
- Embedded description bytes: `80`
- Embedded description:
  `Network trained with the https://github.com/ianfab/variant-nnue-pytorch trainer.`

The owner-provided file and a fresh download from the
[official Fairy-Stockfish network index](https://fairy-stockfish.github.io/nnue/)
are byte-identical. The index labels this file as the current Antichess network,
dated 2024-09-17 and authored by Fabian Fichter. Its displayed `+200 Elo vs.
classical` is upstream context only; it is not Antichess-Stockfish strength
evidence.

The same index states that networks dated 2026 or later are CC0. It does not
establish a redistribution license for this 2024 file. No repository-wide
license file exists at either the current pinned trainer commit
`b15df38a9aae8ab9b40b2378020b3099c7c5d179` or the last trainer commit preceding
the network date, `8f7d7e3699d76bf62c176dad38e5fb85ee4ed3e6`.
Therefore the redistribution license is **unresolved** and the project fails
closed at the distribution boundary.

## Frozen container and evaluation contract

The loader accepts exactly this legacy family:

| Field | Required value |
| --- | --- |
| File version | `0x7AF32F20` |
| Architecture hash | `0x3C103E72` |
| Feature-transformer hash | `0x5F2348B8` |
| Layer-stack hash | `0x633376CA` for every stack |
| Description maximum | 4,096 bytes |
| Payload after description | 953,168 bytes |
| Trailing bytes | forbidden |

The physical feature domain has 768 entries: six piece types, two colors
relative to the current perspective, and 64 relative squares. Antichess kings
are non-royal but remain physical pieces in the king feature plane. The feature
transformer has 512 outputs. The network has eight material-count buckets and
eight `1024 -> 16 -> 32 -> 1` layer stacks. For a non-empty position, the stack
index is `min((piece_count - 1) * 8 / 32, 7)` using integer division.

Evaluation performs two full refreshes, first from the side-to-move perspective
and then from the opponent perspective. It applies the exact legacy clipping,
quantization, PSQT perspective difference, padded layer strides, and output
scaling. This ADR makes no incremental-update, SIMD, training-format, or NNUE
V2 compatibility claim.

## Executable compatibility reference

- Repository: `https://github.com/fairy-stockfish/Fairy-Stockfish.git`
- Commit: `c19b5f6c66894fdb0e88d0dd100e3885f744760a`
- Tree: `5f243edc1ec2498610b3ed40923cf99718104fc8`
- Probe binary bytes: `4,509,974`
- Probe binary SHA-256:
  `8fe05c431e34478ac4248ea0786d6a33ba766c34b3313098b9af00e442c00a56`
- One-line probe diff bytes: `329`
- One-line probe diff SHA-256:
  `b4fdf6fb9807b7c730763fc25da4e41a6285ba8c83a362ae9e18fb97ae63f816`

The probe changes the reference `eval` command to print the raw
`Eval::NNUE::evaluate(position, false)` value. It is not a rules authority,
match referee, candidate source, comparator, or strength baseline.

Exact parity currently covers 40 unique physical positions from the frozen
rules contract plus 18 frozen evaluator positions, including both
side-to-move perspectives and all eight material buckets. All 58 raw values
match the pinned executable.

## Fail-closed evidence

The positive loader test pins the exact file size and SHA-256, description
length, start-position raw value, and a completed search. Negative tests reject
mutated version, architecture, description framing, feature-transformer hash,
layer-stack hash, truncation, and appended bytes. Each rejected file leaves no
network identity or payload active, refuses evaluation and search, and returns
`bestmove (none)`. A valid-then-invalid reload also clears the valid network.

## Consequences and release boundary

- The owner can use the known legacy network locally with the new engine while
  a stronger, properly licensed Antichess network is developed.
- A filename or matching header is never sufficient compatibility evidence.
- The legacy file cannot become a bundled default, release asset, or
  `Antichess_v1.nnue` alias under the current evidence.
- NNUE V2 must use a separately versioned Antichess container and prove scalar,
  SIMD, incremental, full-refresh, make/undo, special-move, and perspective
  parity before promotion.
