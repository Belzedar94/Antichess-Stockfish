# P7 Antichess TT512 v1 r2 preregistration

## Status

**LOCAL ONE-SHOT CANDIDATE COMPARISON PASS. INHERITED CORRECTNESS, OFFICIAL CI,
REVIEW, MERGE, AND POST-MERGE CLOSURE REMAIN OPEN.**

This is deterministic fixed-work engineering evidence only. It is not speed,
Elo, strength, OpenBench, DATAGEN, model-selection, release, or monitoring
evidence, and it authorizes no game.

## Source and asset boundary

- Rules profile: `LICHESS_ANTICHESS_V1`.
- Official Stockfish ancestor:
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`.
- Candidate parent and r1 rejection commit:
  `157213b8d6a0efca33d847fff90bf70262c985ae`.
- Candidate parent tree:
  `632d1483a9c08f362649ddc11149caedeb7c3405`.
- Closed clocked engine merge:
  `89bccf20f0ed197125c8e92b36057ec2e9373a99`.
- No-TT comparator implementation commit:
  `aea46065e72ebcb11f28eb9e8b1bacfad258f535`.
- No-TT comparator Windows binary SHA-256:
  `ba17e95b257528fa3eec28b5f0e8e16d1c856dffc701117fe704d992086f4b0b`.
- Local-only legacy network SHA-256:
  `dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc`.
  It is not redistributed, embedded, made a default, or renamed.

Fairy-Stockfish is neither source ancestry nor a rules authority and is not
used by this experiment.

## Prior rejection

R1 was rejected before candidate implementation because its complete ordered
history key distinguished every path that could form a real transposition.
No r1 candidate build or search occurred. R2 does not amend r1; it is a new
hypothesis, fixture identity, runner identity, comparator record, and receipt.

## One hypothesis

A bound-safe Antichess TT restricted to nodes with at most three remaining
plies can deliberately ignore history states seen only once while preserving
all possible claim and automatic-draw outcomes. With an exact canonical
summary of states already seen at least twice, it will preserve every no-TT
root score and best move and reduce aggregate Hash-512 nodes by at least 15%.

The independent variable is TT probe/store/cutoff reuse at remaining depths
zero through three, plus honest UCI Hash capacity through 512 MiB. The default
`exhaustive-v1` path remains unchanged and TT-free.

## Three-ply safety proof

A repeated full position includes the board, side to move, castling rights,
and en-passant state. An identical full position cannot recur within fewer
than four plies:

- after two plies, each color has moved once;
- the second mover cannot restore the first mover's changed piece;
- captures and promotions are irreversible;
- castling changes two same-color pieces and cannot be restored by the other
  color; and
- no drops or null moves exist in the dedicated search.

Within at most three future plies, a historical position seen exactly once can
therefore be encountered at most once. Its count can rise only from one to two,
which cannot trigger a threefold claim or a fivefold automatic draw. A state
already seen two or more times can affect an outcome with one future encounter,
so its exact count must be retained. Current terminal, automatic-draw, and
claim status is resolved before TT access.

Consequently, for `remaining <= 3`, two nodes are history-equivalent when they
have the same raw current board key, exact rule50 value, and canonical sorted
multiset of `(raw StateInfo key, exact count)` pairs whose count is at least
two over the known reversible history. States with count one are deliberately
omitted. For `remaining > 3`, r2 neither probes nor stores.

This proof does not authorize TT reuse at depth four or greater. Any expanded
horizon requires a new preregistration.

## Frozen context key

The dedicated 64-bit key contains:

1. current raw `StateInfo::key`;
2. exact `rule50`;
3. every repeated-history `(raw key, count)` pair with count at least two,
   sorted by raw key; and
4. the number of retained pairs.

The reversible window is the available chain through
`min(rule50, pliesFromNull)`. Pair order is canonical and independent of path
order. A deterministic avalanche mixer folds the canonical sequence into the
existing Stockfish `Key`. Only ordinary finite-key and TT-cluster collision
risk is accepted.

The key is recomputed at a probe/store boundary. R2 adds no rolling state and
no null move. Two unique-history move orders that reach the same board with the
same rule50 value must produce the same key. Claim histories, different repeat
counts, rule50 values, and en-passant states must remain distinct.

## Reused infrastructure and stored data

R2 may reuse only official Stockfish TT allocation, cluster indexing,
replacement, generation, and hashfull plumbing. It does not enter or copy the
orthodox search path.

Each entry stores only the r2 context key, mate-distance-normalized value,
remaining depth, and exact/lower/upper bound. Stored move is `Move::none()`,
stored evaluation is `VALUE_NONE`, and PV is false. There is no TT move
ordering, window tightening, static-eval cache, tablebase mapping, orthodox
rule50 downgrade, or WDL conversion.

After deadline, terminal, automatic-draw, and claim handling, a usable entry
requires `stored depth >= remaining`. It returns only for exact, lower value at
least beta, or upper value at most alpha. Fully resolved leaves may be stored.
Interrupted or partial nodes may not be stored. Decisive scores use only the
existing root-ply normalization: store win plus ply/loss minus ply; load the
inverse.

## UCI lifetime and diagnostics

- UCI Hash becomes default/minimum/maximum `1/1/512`.
- Invalid Hash values 0 and 513 remain ignored by the existing option parser.
- `new_search()` runs once per Antichess root search.
- Entries may persist between `go` commands in one game.
- `ucinewgame`, `Clear Hash`, Hash resize, evaluator change, and successful or
  failed `EvalFile` load clear TT state and Antichess counters.
- The closed deterministic bench remains pinned to Hash 1.

`antichess-info` exposes `tt_enabled`, `tt_horizon=3`, `tt_context_key`, probes,
key hits, usable hits, cutoffs, stores, maximum remaining depth accessed, and
current-generation hashfull. `tt_max_remaining` must never exceed three and
must reset to zero with the other counters.

## Frozen execution

Fixture:
`tests/antichess/fixtures/p7-antichess-tt512-v1-r2-prereg.json`.
Runner: `tools/search/verify_antichess_tt512_v1.py` at its r2 hash.

After this preregistration is committed and pushed:

1. execute the exact no-TT comparator phase once with Hash 1 and dd3c;
2. freeze record, transcript, invocation, and hashes in a new E1 addendum;
3. only then implement r2 in a separate commit;
4. freeze candidate commit/tree, toolchain, two clean byte-identical Windows
   builds, binaries, and logs before comparison; and
5. execute exactly one candidate invocation containing Hash 1, Hash 512,
   protocol/reset, context relation, and warmed-isolation phases.

No result-aware corpus, threshold, horizon, or stopping change is permitted.

## Fixed decision rule

PASS requires:

- all frozen hashes and identities match;
- Hash 1 and Hash 512 exactly match every comparator score type, score, and
  best move;
- neither candidate configuration exceeds comparator nodes in any case;
- Hash 512 reduces aggregate nodes by at least 15%;
- Hash 512 aggregate nodes do not exceed candidate Hash 1;
- every activity-required Hash-512 case reports probes and stores;
- at least two signal cases report a cutoff, with positive aggregate usable
  hits and cutoffs;
- every accessed TT node reports remaining depth no greater than three;
- UCI Hash and all reset/invalidation contracts pass;
- unique-history transposition keys are equal, while claim history, exact
  repeat count, rule50, and en-passant distinctions pass;
- warmed claim and rule50 histories cannot change a fresh raw score/bestmove;
- inherited rules, parser, notation, claim-horizon, loader, scalar parity,
  deterministic bench, reproducibility, and sanitizers pass; and
- official Stockfish remains an ancestor and Fairy-Stockfish remains outside
  ancestry.

Any mismatch, horizon violation, per-case node increase, aggregate reduction
below 15%, isolation failure, crash, stall, timeout, dirty build, or inherited
regression rejects r2 without retuning or repetition.

## Exclusions and non-claims

R2 excludes orthodox search, TT move ordering, aspiration, SEE, null move,
qsearch, LMR, extensions, history ordering, all other pruning, evaluator or
rule changes, and result adjudication.

A PASS admits only FSF/book/referee and panel-harness certification before any
three-time-control game. It does not establish strength, start a game, change
the default search, authorize OpenBench, or authorize a release.

## Recorded local comparison

The exact one-shot candidate comparison passed on 2026-09-01. All 14 Hash-1
and Hash-512 candidate records matched the frozen comparator score type, score,
and best move, and no candidate case exceeded its comparator node count.

- comparator aggregate nodes: 1,453,898;
- candidate Hash-1 aggregate nodes: 932,063;
- candidate Hash-512 aggregate nodes: 924,190;
- Hash-512 reduction versus comparator: 36.433642525129%;
- Hash-512 usable hits: 225,429;
- Hash-512 cutoffs: 217,606;
- signal cases with a cutoff: 6; and
- maximum TT remaining depth observed: 3.

The frozen context-key relations, warmed-history isolation, Hash range,
invalid-value persistence, and every required reset/invalidation check passed.
The local record SHA-256 is
`c1ae8a015366ac7e48cc7dca9d9b1b69dcb76fbf67aa6f49338f38228eb4e4e5`.
The one-shot attempt is consumed and must not be repeated or retuned.

This result admits inherited local correctness and official CI only. It is not
timing, Elo, strength, OpenBench, DATAGEN, model-selection, release, or
monitoring evidence, and it does not admit the three-time-control panel.
