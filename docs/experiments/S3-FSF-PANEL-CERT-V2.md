# S3 Fairy-Stockfish panel-input certification v2 addendum

## Status

**EXECUTED ONCE AND PASSED. NO STRENGTH GAME HAS RUN.**

The first certification execution stopped during the Fairy-Stockfish negative
network probe. The synthetic filename `missing-fsf-network.nnue` did not match
the comparator's `antichess` filename selector, so the comparator deliberately
disabled NNUE, announced classical evaluation, and searched. That observation
is loader-routing evidence only. The execution stopped before focused legality,
the 202-position book audit, and the two-game plumbing smoke.

V2 changes exactly one experimental input: the nonexistent comparator network
basename becomes `antichess-missing-fsf-network.nnue`. It remains nonexistent,
but it now preserves the same variant-selection predicate as the positive
`antichess-dd3cbe53cd4e.nnue` input. The expected outcome is a nonzero process
exit, explicit required-network error, and no best move.

The candidate source and binary, Fairy-Stockfish comparator, real network,
opening suite, referee, 879 checks, legal-set requirements, deterministic
schedule, smoke, and every panel threshold remain byte-for-byte or
semantically unchanged from v1. V1 is not retried. V2 receives a new
implementation freeze and a new single execution identity before it runs.

A V2 pass remains engineering/correctness evidence that admits only a separate
final S3 strength preregistration. It is not Elo, LOS, OpenBench, model
selection, DATAGEN, release, or monitoring evidence.

## Frozen result

V2 ran once on 2026-09-01 after implementation commit `5d0786d8`, immutable
freeze commit `fd0d1249`, and exact-head CI run `33473386881` passed. The
certification result SHA-256 is
`5a5a9600cd2ae455c0daefce7b91c12fb73d4280c57e7d195c235551eba01ae5`.

- All 56 focused positions had exact candidate/comparator/referee legal-set
  agreement; 14 contained compulsory captures.
- All 202 opening positions had exact three-way legal-set agreement; 103
  contained compulsory captures.
- Both positive network probes loaded the exact `dd3c` bytes. Both negative
  probes failed closed without producing a usable search result.
- The 879-check `AC_REFEREE_V1` verification passed.
- The color-swapped forced-terminal plumbing smoke produced two audited games,
  two legal compulsory captures, no illegal move, crash, disconnect, stall,
  timeout, or time loss. Those games are explicitly not strength evidence.

The pass closes panel-input certification only. The final VSTC/STC/LTC runner,
schedule, stopping rule, invalidation policy, and resource lease must be frozen
under a separate strength preregistration before the first strength game.
