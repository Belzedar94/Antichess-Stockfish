# S3 Fairy-Stockfish panel-input certification v2 addendum

## Status

**PREREGISTERED BEFORE THE V2 CODE CHANGE. V2 HAS NOT RUN, AND NO STRENGTH
GAME IS AUTHORIZED.**

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
