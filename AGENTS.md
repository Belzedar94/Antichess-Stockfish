# Antichess-Stockfish project rules

These rules are authoritative for this repository.

- The only production rules profile is `LICHESS_ANTICHESS_V1`. Never infer
  semantics from the generic words antichess, suicide, giveaway, or losers.
- The source base is official Stockfish development commit
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`. No Fairy-Stockfish commit or
  implementation file may enter candidate ancestry.
- Files copied from the rejected lineage are limited to the hashed contract
  allowlist in `docs/provenance/OFFICIAL_STOCKFISH_BASE.md`. Any implementation
  must be written and reviewed against primary sources and differential
  fixtures.
- Do not change strength behavior, tune search, run Elo tests, generate data,
  train a model, or use fleet resources until P6 passes in
  `docs/gates/GATE_INDEX.md`.
- Candidate output may not define expected fixture results. Keep primary
  authority, executable references, independent referee, and candidate roles
  separate.
- Receipts are append-only. Never edit or delete a committed file under
  `receipts/`; add a new receipt or addendum.
- Never commit NNUE bytes. The known legacy network is local-only and
  diagnostic-only until its exact format, feature domain, compatibility, and
  redistribution license are proven.
- Only `https://belzedar.duckdns.org` is official OpenBench. No Antichess job is
  allowed there until the exact client/server/referee mapping passes the same
  frozen differential fixtures and resources have an explicit lease.
- Public documentation, commits, pull requests, releases, and announcements
  must be written in English.

## Build and verification

Run engine build commands from `src/`.

```sh
make -j2 ARCH=x86-64 COMP=mingw COMPCXX=/mingw64/bin/g++ build
python tools/reference/verify_fixture_contract.py
```

The upstream Stockfish test suite remains relevant but cannot certify the
Antichess dialect, terminal rules, referee, assets, or strength.
