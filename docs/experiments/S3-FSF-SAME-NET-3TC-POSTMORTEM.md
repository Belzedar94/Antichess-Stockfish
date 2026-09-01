# S3 Fairy-Stockfish same-network panel post-mortem

## Outcome

The current Antichess-Stockfish candidate is `REJECTED_STRENGTH`.

VSTC stopped at the first preregistered eligible boundary: 51 complete
color-swapped pairs, 102 games, candidate W/L/D 1/101/0, and displayed LOS
`0.0%`. STC and LTC were not started. This is the required behavior after the
candidate-loss gate; extending the sample would be optional stopping.

## What the result establishes

- The exact candidate lost the frozen whole-engine comparison against the
  exact Fairy-Stockfish comparator at VSTC.
- Both engines loaded the same `dd3c` bytes. The result therefore does not
  compare networks and cannot be blamed on a network mismatch.
- All games used `LICHESS_ANTICHESS_V1` through `AC_REFEREE_V1`, the same
  frozen opening schedule, one thread, Hash 512, engine restart per game, and
  concurrency one.
- The result is valid strength evidence: 255 pair-artifact hashes and sizes
  reverified, all PGNs replayed, all 3,918 plies had clock comments, and the
  audits found zero illegal moves, result disagreements, time losses, crashes,
  disconnects, stalls, or controller timeouts.

## What the result does not establish

It does not identify a single causal search defect, measure NNUE quality,
validate another time control, authorize DATAGEN or NNUE V2, or support a
release. It also does not make Fairy-Stockfish a source or rules authority.

Raw VSTC traces provide a diagnostic boundary, not a causal attribution. Across
terminal search records, the candidate's median reported depth was 7 and median
NPS was about 455 thousand; Fairy-Stockfish reported median depth 15 and median
NPS about 819 thousand. Median reported search time was 56 ms for the candidate
and 32 ms for the comparator. Depth and node semantics differ between engines,
so these figures may motivate engineering investigation but cannot be converted
into an Elo explanation or a parameter-tuning rule.

## Rejected inference

The project assumed that a current official-Stockfish base plus a dedicated
Antichess implementation would readily overcome Fairy-Stockfish's multi-variant
overhead. That assumption was not evidence. The implemented dedicated search
was intentionally narrow: correctness-preserving alpha-beta, clocked iterative
deepening, and a bounded transposition table. Its exact-score and node-reduction
gates did not demonstrate equivalence to a mature variant search.

## Next safe action

Preserve this panel as a consumed holdout. Do not replay it, extend it, filter
its openings, or tune parameters against its outcomes. The next engineering
step may preregister one structural search hypothesis, using independent
correctness and fixed-work fixtures to select the design. Before another
strength claim, freeze a new experiment identity and an untouched validation
policy, then repeat review, reproducibility, ancestry, referee, authorization,
and exclusive-lease gates.

P8, NNUE V2, OpenBench, release, and publication remain closed. A stable release
still requires a complete verified draft and explicit owner G15 approval.
