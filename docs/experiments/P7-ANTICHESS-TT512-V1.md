# P7 Antichess TT512 v1 preregistration

## Status

**PREREGISTERED. No candidate implementation exists, no comparator record has
been generated, and the one-shot candidate comparison has not been executed.**

This is a deterministic fixed-work engineering experiment. It is not Elo,
strength, speed, OpenBench, DATAGEN, model-selection, release, or monitoring
evidence. It does not authorize a game.

## Frozen source boundary

- Rules profile: `LICHESS_ANTICHESS_V1`.
- Official Stockfish source ancestor:
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`.
- Candidate parent and clocked-search governance merge:
  `930747bb6b0426d3fa343d711e7ef61122bb6390`.
- Candidate parent tree:
  `b923f892f947e02e762de545cd4a8a97e3ebd510`.
- Closed clocked engine merge:
  `89bccf20f0ed197125c8e92b36057ec2e9373a99`.
- No-TT comparator implementation commit:
  `aea46065e72ebcb11f28eb9e8b1bacfad258f535`.
- No-TT comparator Windows binary SHA-256:
  `ba17e95b257528fa3eec28b5f0e8e16d1c856dffc701117fe704d992086f4b0b`.
  The `src` tree is byte-identical between that implementation commit and the
  candidate parent; the intervening commits contain evidence and governance
  files only.
- External legacy network SHA-256:
  `dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc`.
  It remains local-only and must not be redistributed, embedded, made the
  default, or renamed as a public alias by this experiment.
- Search mode: `alpha-beta-v1`; threads: 1.

Fairy-Stockfish is neither source ancestry nor a rules authority. It is not
used anywhere in this fixed-work experiment.

## One hypothesis

A dedicated Antichess transposition table using history-complete context keys
and bound-safe cutoffs will preserve every no-TT root score and best move while
reducing aggregate fixed-depth nodes by at least 15%. A 512 MiB UCI Hash
setting will be honestly allocated and will not perform more aggregate work
than the same candidate with a 1 MiB table.

The independent variable is only Antichess TT probing, storing, and cutoff
reuse in `alpha-beta-v1`, together with the UCI capacity needed to select 512
MiB. The default `exhaustive-v1` path remains TT-free and unchanged.

## Reused infrastructure boundary

The implementation may reuse only the official-Stockfish
`TranspositionTable` allocation, cluster indexing, replacement, generation,
and `hashfull` plumbing already present in the official source line. It must
not enter or copy the orthodox search path or inherit orthodox TT semantics.

Antichess v1 stores only:

- a history-complete Antichess context key;
- a mate-distance-normalized value;
- the remaining depth;
- `BOUND_EXACT`, `BOUND_LOWER`, or `BOUND_UPPER`.

The stored move is always `Move::none()`, the stored evaluation is always
`VALUE_NONE`, and the PV flag is false. No TT move ordering is permitted.

## Frozen history-complete key

The ordinary board key is insufficient because threefold claims, automatic
fivefold draws, and the 50-move boundary depend on history. The candidate must
add a dedicated Antichess context key with these inputs:

1. the current raw `StateInfo::key`, including side, castling rights, and en
   passant state;
2. the exact `rule50` value;
3. `min(rule50, pliesFromNull)`;
4. every available raw `StateInfo::key`, in exact newest-to-oldest order,
   through that reversible-history limit; and
5. the number of history states actually available.

The sequence is deliberately order-sensitive. Histories that happen to have
the same multiset but a different order may miss a reusable entry; they must
not be deliberately aliased. A deterministic 64-bit avalanche mixer may fold
the sequence into the existing `Key` type. Ordinary finite-key and TT-cluster
collision risk remains the only accepted aliasing risk.

The v1 key is recomputed from `StateInfo` at a probe/store boundary. No rolling
history cache, null-move state, or new incremental state field is introduced.
The dedicated search does not make null moves.

## Frozen node semantics

The semantic order remains:

1. deadline check and node accounting;
2. Antichess variant terminal;
3. Antichess automatic draw;
4. claimability calculation;
5. TT probe using the dedicated context key;
6. depth-zero evaluation and claim floor when no usable exact entry exists;
7. at internal nodes, claimable draw as the existing virtual score-zero option;
8. sorted legal mandatory-capture moves and the existing alpha-beta recursion.

A hit is usable only when its stored depth is at least the requested remaining
depth and its value is valid. A usable entry may return immediately only when:

- its bound is exact;
- it is a lower bound whose value is at least beta; or
- it is an upper bound whose value is at most alpha.

The candidate must not tighten alpha or beta from a non-cutting entry. Terminal
and automatic-draw nodes are resolved before TT access. Interrupted nodes and
partially searched nodes must never be stored. Fully resolved leaf evaluations
may be stored at depth zero.

The original effective alpha after applying the claim floor is frozen for
bound classification. A fully resolved value is stored as lower when it is at
least beta, upper when it is no greater than that frozen alpha, and exact
otherwise.

Decisive values are normalized only for root-ply distance:

- store a win as `value + ply` and a loss as `value - ply`;
- load a win as `value - ply` and a loss as `value + ply`.

No orthodox rule-50 downgrade, tablebase range, checkmate interpretation, WDL
conversion, static-eval cache, or correction-history assumption is imported.

## Frozen lifetime and invalidation

- Call `new_search()` once at the beginning of each Antichess root search.
- Preserve valid entries between `go` commands in the same game.
- `ucinewgame`, `Clear Hash`, a Hash resize, any evaluator selection change,
  and every successful or failed `EvalFile` load must clear the TT and its
  Antichess counters before reuse.
- `exhaustive-v1` neither probes nor stores TT entries.
- An interrupted clocked iteration may leave entries only from nodes that had
  already completed; its interrupted call chain stores nothing.

The UCI `Hash` option changes from default/minimum/maximum `1/1/1` to
`1/1/512`. Invalid spin values are ignored by the existing UCI option parser.
The deterministic `bench` command remains pinned to Hash 1 so its closed digest
does not silently change.

## Frozen diagnostics

`antichess-info` must expose the selected `hash_mb`, the current
`tt_context_key`, and per-root counters for probes, key hits, depth-usable hits,
cutoffs, and attempted stores. It must also expose whether TT is enabled and
the current-generation `tt_hashfull` value.

The final UCI `info` line reports the same current-generation hashfull when TT
is enabled and zero under `exhaustive-v1`. Diagnostics are capability evidence,
not Elo.

## Frozen execution

The fixture is
`tests/antichess/fixtures/p7-antichess-tt512-v1-prereg.json`; the direct UCI
runner is `tools/search/verify_antichess_tt512_v1.py`.

After this preregistration is committed and pushed:

1. run the exact no-TT comparator once with Hash 1 and the exact external
   network;
2. retain every raw transcript, score, best move, and node count;
3. freeze the comparator record and its SHA-256 in an immutable E1 addendum;
4. only then implement the candidate in a separate commit;
5. freeze the exact candidate commit, tree, toolchain, dual clean build logs,
   and byte-identical Windows binary before comparison; and
6. execute one candidate-comparison invocation containing the frozen Hash 1
   control, Hash 512 candidate, protocol probes, context-key relations, and
   isolation probes.

There is one planned candidate comparison. No result-aware case, depth,
threshold, capacity, or stopping-rule change is permitted.

## Fixed decision rule

PASS requires all of the following:

- the comparator, candidate, fixture, runner, and external network hashes match
  their frozen identities;
- candidate Hash 1 and Hash 512 both match every comparator score type, score,
  and best move exactly;
- neither candidate configuration visits more nodes than the comparator in any
  case;
- Hash 512 visits at least 15% fewer aggregate nodes than the comparator;
- Hash 512 aggregate nodes are no greater than candidate Hash 1 aggregate nodes;
- all nonterminal Hash 512 cases report probes and stores;
- the frozen transposition-signal group reports cutoffs in at least two cases
  and reports at least one aggregate usable hit and cutoff;
- the UCI Hash contract is exactly default 1, minimum 1, maximum 512, persists
  through `isready`, and ignores values 0 and 513;
- `Clear Hash`, `ucinewgame`, evaluator switches, and successful or failed
  network loads reset TT state and counters;
- raw-board, claim-history, rule50, en-passant, and deterministic-repeat
  context-key relations match the frozen fixture;
- warmed claim-history and rule50 searches cannot change the exact fresh raw
  score or best move;
- the default search remains `exhaustive-v1` and remains TT-free;
- the complete inherited rules, parser, notation, claim-horizon, loader,
  scalar-parity, deterministic-bench, reproducible-build, and sanitizer gates
  pass; and
- official Stockfish remains an ancestor while Fairy-Stockfish remains outside
  ancestry.

Any mismatch, per-case node increase, aggregate reduction below 15%, missing
capacity or diagnostic handshake, isolation failure, invalid/incomplete record,
crash, stall, timeout, dirty build, or inherited regression rejects the
hypothesis without retuning or repetition. A changed hypothesis requires a new
branch and a new preregistration.

## Explicit exclusions and non-claims

This hypothesis must not add or enable the orthodox search path, TT move
ordering, aspiration, SEE, null move, qsearch, LMR, extensions, history
ordering, any additional pruning, evaluator changes, rule changes, or result
adjudication.

A PASS admits only comparator/book/referee certification and sealing of the
same-network three-time-control panel. It does not establish strength, make
`alpha-beta-v1` the default, start a game, authorize OpenBench, or authorize a
release.
