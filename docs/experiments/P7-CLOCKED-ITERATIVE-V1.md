# P7 clocked iterative deepening v1 preregistration

## Status

**PREREGISTERED. Candidate implementation does not exist and the clock-scaling
experiment has not been executed.**

This is an engineering and timing-capability experiment. It is not Elo,
strength, OpenBench, DATAGEN, model-selection, release, or monitoring evidence.
No game may be started from this experiment.

## Frozen source boundary

- Rules profile: `LICHESS_ANTICHESS_V1`.
- Official Stockfish source ancestor:
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`.
- Candidate parent and readiness-boundary merge:
  `f7b0f22659ffbe6c1fb1704269bd811d8b5cc22c`.
- Closed alpha-beta engine merge:
  `fcdd4f0ecf2b397b24dad426d940526b3160241f`.
- Parent Windows binary SHA-256:
  `1dfc55b2c9d1c37f459d425f345710d76600594e48d21e8bd90e2907abf42fac`.
- Parent fixed-work record SHA-256:
  `acf19303c56dfcda4eddfc4ae254305ac7f5c3548404d9dc0d63e7fbde503e8c`.
- External legacy network SHA-256:
  `dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc`.
  It remains local-only and must not be redistributed, embedded, made a
  default, or renamed as a public alias by this experiment.
- Search mode: `alpha-beta-v1`; threads: 1; Hash: 1 MiB.

Fairy-Stockfish is not source ancestry or a rules authority. Hash 512 and an
Antichess transposition table remain a later, separate preregistered
hypothesis.

## One hypothesis

For clock-controlled UCI searches only, completed-iteration iterative
deepening over the existing dedicated Antichess alpha-beta search will make
the amount of searched work increase materially from VSTC to STC to LTC while
returning before a conservative hard deadline. Explicit fixed-depth searches
will preserve every frozen score, best move, and node count.

The independent variable is only the clock-controlled outer iterative loop
and its deadline checks. The recursive evaluator, terminal precedence,
claim handling, move generator, sorted UCI move order, independent full-window
root searches, alpha-beta windows, and root tie rule remain unchanged.

## Frozen command classification

1. If `go depth N` supplies a positive depth, retain the current single
   fixed-depth path and clamp `N` to 1 through 8. Clock fields on the same
   command do not change that fixed-depth result.
2. Otherwise, enter clocked mode only when `movetime` is positive or the
   side-to-move clock is positive.
3. `go nodes`, `go mate`, `go infinite`, and an unconstrained `go` remain
   outside this hypothesis and retain the parent depth-4 fallback.
4. Pondering and asynchronous `stop` handling are not added here.

This precedence keeps every inherited fixed-depth verifier independent from
host timing and prevents this experiment from silently broadening into a UCI
protocol rewrite.

## Frozen time budget

All arithmetic below is integer milliseconds. The fixed overhead is 20 ms.

- For `movetime M`, the hard budget is `max(1, M - 20)`.
- For a game clock, let `T` be the side-to-move time, `I` its increment, and
  `H` be `clamp(movestogo, 1, 50)` when supplied or 40 otherwise.
- The hard budget is
  `min(max(1, T - 20), max(1, T / H + (3 * I) / 4))`.
- The hard deadline is `limits.startTime + hard_budget`.
- Clocked iterative deepening is capped at depth 64.

The owner-selected panel clocks therefore map exactly to:

| Rung | Clock | Increment | Frozen hard budget |
| --- | ---: | ---: | ---: |
| VSTC | 2,000 ms | 20 ms | 65 ms |
| STC | 10,000 ms | 100 ms | 325 ms |
| LTC | 30,000 ms | 300 ms | 975 ms |

These are capability probes, not the final panel settings contract. They do
not authorize games.

## Frozen interruption semantics

- Check the deadline before each new iteration and before each root move.
- During recursive search, check the deadline every 64 node visits.
- Always undo the current move before propagating an interrupted search.
- Discard an interrupted iteration completely. Only the score and best move
  from the last fully completed iteration may be reported.
- Count nodes from completed iterations and the discarded partial iteration
  in the final UCI node total.
- If no depth-1 iteration completes, return the sorted first legal root move
  as a depth-0 fallback; the experiment then fails.
- Terminal and automatic-draw handling before iterative search remains
  unchanged.

No soft deadline, aspiration window, previous-PV move ordering, time
prediction, result-aware extension, or per-position tuning is permitted.

## Frozen verification

The fixture is
`tests/antichess/fixtures/p7-clocked-iterative-v1-prereg.json`; the direct UCI
runner is `tools/search/verify_clocked_iterative_v1.py`.

The fixed-depth phase uses the engineering-neutral evaluator and replays the
13 closed P7 cases at depth 4. Every score type, score, best move, and node
count must equal the frozen parent record.

The clock-scaling phase uses the exact external `dd3c` bytes with
`legacy-v1`, the start position, three repetitions, and the preregistered
balanced rung orders:

1. VSTC, STC, LTC;
2. LTC, VSTC, STC;
3. STC, LTC, VSTC.

A separate 250 ms `movetime` probe verifies that this UCI clock form reaches
the same clocked path. Raw UCI transcripts and per-search wall time, engine
time, depth, nodes, score, and best move must be retained.

## Fixed decision rule

PASS requires all of the following in the first and only clock-scaling
execution:

- the exact engine, fixture, runner, and network hashes match the frozen
  invocation;
- all 13 fixed-depth cases exactly match score type, score, best move, and
  nodes;
- every clocked search completes at least depth 1 and returns a legal-looking
  non-null UCI best move;
- every wall time and engine-reported time is no greater than its hard budget
  plus 250 ms;
- every game-clock probe returns before its supplied base time;
- aggregate nodes satisfy `STC / VSTC >= 1.50` and
  `LTC / STC >= 1.50`;
- median completed depth is nondecreasing across the three rungs and the LTC
  median is strictly greater than the VSTC median;
- the full inherited rules, parser, notation, search, repetition,
  claim-horizon, loader, scalar-parity, deterministic-bench, reproducible
  build, and sanitizer gates pass; and
- official Stockfish remains an ancestor while Fairy-Stockfish remains
  outside ancestry.

Any mismatch, timeout, crash, missing output, budget overrun, insufficient
work scaling, dirty build, inherited regression, or incomplete record rejects
this hypothesis without retuning or repetition. A changed budget, overhead,
check interval, corpus, ratio, or stopping rule requires a new branch and a
new preregistration.

## Explicit exclusions and non-claims

This hypothesis must not add or enable the orthodox search path, a
transposition table, Hash above 1 MiB, SEE, null move, qsearch, LMR,
extensions, aspiration, history ordering, additional pruning, evaluator
changes, rule changes, or result adjudication.

A PASS admits only a separate Hash-512/Antichess-TT preregistration. It does
not admit the Fairy-Stockfish match, establish strength, change the default
search option, or authorize a release.

## Recorded outcome

The hypothesis passed its first and only clock-scaling execution. The frozen
VSTC/STC/LTC aggregate node counts were 52,032, 262,208, and 795,648; the
adjacent ratios were 5.0394 and 3.0344, and median completed depths were 3, 4,
and 5. The separate `movetime` probe completed depth 4 within its frozen
budget. No time loss, timeout, crash, or inherited correctness failure was
observed.

Pull request #8 merged the exact reviewed head as
`89bccf20f0ed197125c8e92b36057ec2e9373a99`; post-merge official run
`33463542558` passed reproducible-build and Linux ASan/UBSan jobs, and its
downloaded artifact was reverified byte-for-byte. The GitHub review record was
persisted after merge rather than before it; that disclosed governance
deviation is tracked as `INC-REVIEW-003` and does not create strength evidence.

The next admitted search work is a new, separately preregistered Antichess
transposition-table hypothesis. `Hash` remains capped at 1 MiB, so the
three-time-control panel remains closed.
