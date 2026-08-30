# P7 alpha-beta v1 preregistration

## Status

This experiment is preregistered but has not been executed. The candidate
implementation does not exist at the time of this record. A foreign project
holds the local exclusive CPU timing lease, so no comparator search, candidate
search, build, timing run, match, or strength run is authorized in this state.

This document is engineering evidence only. It is not Elo, strength,
OpenBench, DATAGEN, model-selection, release, or monitoring evidence.

## Identities

- Rules profile: `LICHESS_ANTICHESS_V1`.
- Source lineage: official Stockfish dev commit
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`.
- Candidate parent: merge commit
  `a6e03ab48f7606580f9b9142e898e6485edc87f3`.
- Comparator source: corrected engineering baseline commit
  `d08cc316fc63d95f1101122ba2450d1eb1aea7f7`.
- Comparator Windows binary SHA-256:
  `dbfcdc98acdb676226f6b2a0c5251291cfafb391e9099f1e3a33eccb0d73d3ca`.
- Evaluator: `engineering-neutral`; no network is loaded.
- Fixture: `tests/antichess/fixtures/p7-alpha-beta-v1-prereg.json`.
- Direct UCI harness: `tools/search/verify_alpha_beta_v1.py`.
- Threads: 1. Hash: 1 MiB. Fixed depth: 4.
- Book, referee, time control, adjudication, games, colors, and opening seeds:
  none, because this is a deterministic fixed-work engineering experiment.

The comparator record, candidate commit, candidate binary hash, build identity,
and execution receipt must be frozen in an addendum before candidate comparison.

## One hypothesis

Within each independently searched root move, a plain fail-soft negamax
alpha-beta window will visit at least 25% fewer aggregate nodes than the exact
exhaustive comparator while preserving every root score and best move on the
frozen corpus.

Each root move remains an independent full-window search. Root move ordering
remains sorted UCI order. The existing root tie rule remains unchanged. This
isolates internal alpha-beta pruning from root ordering, aspiration, or
result-aware extension effects.

## Frozen semantics

The candidate may add one UCI combo option:

`Antichess_Search`, with values `exhaustive-v1` and `alpha-beta-v1`.

The default must remain `exhaustive-v1` until all promotion gates pass. The
candidate changes only the recursive window and cutoff mechanism selected by
`alpha-beta-v1`. It must not enable or introduce:

- the orthodox `src/search.cpp` path;
- transposition-table cutoffs;
- SEE, null move, quiescence search, reductions, extensions, or pruning other
  than plain alpha-beta;
- orthodox material, king safety, mate legality, or WDL semantics;
- move-order changes, evaluator changes, terminal changes, claim changes, or
  protocol changes.

Node precedence remains exact:

1. variant terminal;
2. automatic draw;
3. depth-zero static evaluation;
4. at depth zero only, floor a claimable negative static value at draw;
5. at internal nodes, treat a claimable draw as a virtual score-zero option;
6. search legal moves under the mandatory-capture move generator.

The root still evaluates every legal root move under a full window and retains
the existing exact tie behavior:

`score > bestScore || (score == bestScore && is_win(score))`.

## Execution order

1. Wait for a verified exclusive local CPU window.
2. Run the exact comparator binary once through the frozen direct UCI harness.
3. Store and hash every comparator score, best move, and node count.
4. Add the comparator record and its hash to an immutable receipt addendum.
5. Only then implement `alpha-beta-v1` in a separate commit.
6. Produce a clean candidate build and freeze its commit, tree, binary hash,
   toolchain, and build log before comparison.
7. Run the candidate once through the same harness and frozen corpus.
8. Run the full P0-P6 fixture, parser, search, claim-horizon, loader, parity,
   notation, bench, reproducibility, and sanitizer gates.

No timing or match rung may be started by this experiment.

## Fixed decision rule

PASS requires all of the following:

- every case has the exact comparator score type and score;
- every case has the exact comparator best move;
- candidate nodes are no greater than comparator nodes for every case;
- aggregate candidate nodes are at least 25% below aggregate comparator nodes;
- all inherited correctness, claim-horizon, build, reproducibility, and
  sanitizer gates pass;
- the implementation commit has the candidate parent above in its ancestry,
  the official Stockfish dev commit remains an ancestor, and the rejected
  Fairy-Stockfish line remains outside ancestry.

Any semantic mismatch, per-case node increase, aggregate reduction below 25%,
invalid or incomplete record, crash, stall, timeout, dirty build, or inherited
gate regression is a local rejection. There is one planned attempt and no
result-aware corpus, depth, threshold, or stopping-rule change. A different
hypothesis requires a new branch and a new preregistration.

PASS would admit only the next separately preregistered gate. It would not make
`alpha-beta-v1` the default and would not establish strength.
