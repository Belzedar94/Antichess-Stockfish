# Official Stockfish source base

## Owner decision

The project owner rejected Fairy-Stockfish as the Antichess-Stockfish source
base and required the latest official Stockfish development head. The rejected
line is historical evidence only and cannot be a candidate ancestor.

## Pinned source identity

- Repository: `https://github.com/official-stockfish/Stockfish.git`
- Branch observed: `master`
- Commit: `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`
- Tree: `8893b88f51de19a44e44b67a72a56aef2ac2e0cc`
- Commit date: `2026-08-29T07:16:46Z`
- Subject: `Peel off one iteration of the halfka incremental update`
- Upstream tag: `stockfish-dev-20260829-8bc5caa2`
- Local annotated base tag: `base/official-stockfish-20260829-8bc5caa2`

The candidate branch was created directly at that commit. It was not merged,
rebased, or cherry-picked from Fairy-Stockfish.

## Pristine control build

The detached official checkout was clean before and after the tracked build.

- Command: `make -j2 ARCH=x86-64 COMP=mingw COMPCXX=/mingw64/bin/g++ build`
- Toolchain: MSYS2 GNU Make and MinGW-w64 GCC, C++17
- Exit status: `0`
- Elapsed: `54,780 ms`, including the clean step and official network download
- Binary bytes: `102,858,438`
- Binary SHA-256:
  `6321fa00ee771fedc024382149e8f1719c901177914c23dd00c54d135b27556b`
- UCI identity: `Stockfish dev-20260829-8bc5caa2`
- Repeated bench: `2,497,913` nodes in both runs

This proves only that the pristine upstream source and local toolchain build.
It is not Antichess correctness or strength evidence.

## Rejected-line preservation

- Archive tag object: `4f916b9df80c6d012ce76e8ecfb1b0760499ef03`
- Archive target: `432632ecd058ee2465b52e38531e8d409ea68804`
- Local bundle bytes: `12,410,392`
- Bundle SHA-256:
  `74d78edf9b57457caffd36eb4ad0839bf5f5d98cb9133cef5e4f4988b5f72904`

## Contract-only import allowlist

The following files crossed the lineage boundary as exact blobs. They contain
rules, fixtures, or independent-reference tooling, never candidate engine
implementation or strength code.

| Path | Git blob |
| --- | --- |
| `RULES/AUTHORITY.lock.json` | `c64d9859a2412e4e580be9231d5b641a624c213a` |
| `RULES/LICHESS_ANTICHESS_V1.md` | `4562948b0a276fe4d5a9974b2900c4e2c6199ef4` |
| `tests/antichess/fixtures/core-v1.json` | `f9599ba9b591794b3989ae36d3fa59d0b70311b1` |
| `tests/antichess/fixtures/material-boundaries-v1.json` | `dee63df32916e1ab5fd7e297ae08fe251fa56c05` |
| `tests/antichess/fixtures/parser-boundaries-v1.json` | `034b952f10b0be86e9a182c367f8bc8a49734c72` |
| `tests/antichess/fixtures/protocol-claim-boundaries-v1.json` | `ec059e3925e73ced65ef7bfc448453a9511eaade` |
| `tests/antichess/fixtures/repetition-boundaries-v1.json` | `d298a62bf9687ae16f78accee5ad46aa96e7c4aa` |
| `tests/antichess/fixtures/search-boundaries-v1.json` | `1c9a7c56d09d3722aa892e99672728c135c4163e` |
| `tools/reference/verify_fixture_contract.py` | `3c7a932a42ca610b32708b9e684fbf7f3dd5db36` |
| `tools/reference/chessops/verify_fixtures.mjs` | `3321417dc3e77f43383fba04254759005a8ad06f` |
| `tools/reference/scalachess/ScalachessProbe.scala` | `ac71dd21e7f9c46e956808f082f36f638a873883` |
| `tools/reference/scalachess/verify_fixtures.py` | `dc755d8b2b21c290732adc21f9e67910fa6524dd` |

Excluded from transfer: C/C++ implementation, Makefiles, binaries, bindings,
candidate verifiers, receipts, networks, books, benchmarks, search parameters,
and CI claims.

## Architecture review

A browser-only ChatGPT Pro review completed against the official-Stockfish port
plan. Transcript SHA-256:
`06ef6356d666fd429d8b15a178e341c0dbe1c4d2e3a0c5f7a7db500b774dbd17`.
It is advisory evidence. Every recommendation still requires local
implementation and verification. The review used an earlier official pin, so
source-sensitive seams are re-audited against `8bc5caa2`.
