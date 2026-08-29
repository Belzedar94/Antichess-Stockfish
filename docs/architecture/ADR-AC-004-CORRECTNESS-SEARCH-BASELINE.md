# ADR-AC-004: Correctness-only search baseline

- Status: accepted for P3/P4 correctness work; not accepted as a strength
  baseline
- Date: 2026-08-29
- Rules profile: `LICHESS_ANTICHESS_V1`

## Decision

The first official-Stockfish-derived Antichess candidate uses a small,
deterministic, exhaustive negamax search only to exercise legal moves,
terminal values, repetition claims, and evaluator compatibility. It is not a
ported Stockfish strength search.

Moves are ordered by their exact UCI string. The search has no transposition
table reads or writes, quiescence search, static exchange evaluation, null
move, pruning, extensions, reductions, orthodox material term, king-safety
term, Syzygy probe, orthodox WDL conversion, or result adjudication. It uses
one thread and exposes a fixed one-megabyte Hash option so a runner cannot
silently request uncertified parallel or TT behavior.

## Score semantics

An internal and UCI `mate` score means signed distance to a forced
Antichess **variant winner**, not checkmate. Positive is favorable to the side
to move; negative is unfavorable. A terminal node is favorable because the
side to move has no piece or no legal move and therefore wins under this
profile. Search fixtures freeze both signs and a forced-win-versus-repetition-
claim case.

The engineering-neutral leaf evaluator is exactly zero. The optional
`legacy-v1` evaluator is full-refresh and side-to-move relative; its raw values
match the pinned executable reference exactly. No orthodox evaluation sign or
label is imported.

An available third-occurrence claim is a virtual zero-valued option, not a
forced leaf: search may continue and choose a forced win. The match service,
not the UCI engine, performs the result-blind claim. Automatic draws return a
zero score with a deterministic legal fallback move when the protocol asks for
one; board-terminal positions return `bestmove (none)`.

## Protocol and resource boundary

`go depth N` is certified for depths one through eight. A `go` command without
an explicit depth uses depth four. Clock fields are accepted and preserved in
the real-pair evidence, but this correctness search does not allocate time from
them and does not establish time-management quality. Its shallow bounded
search is intentionally synchronous. Strength, stop/ponder behavior, clean
timing, speed, and OpenBench readiness remain gated for later search work.

The UCI surface omits Ponder, MultiPV, Skill Level, Chess960, Syzygy, and WDL
options because none has an Antichess fixture-backed implementation. The exact
public variant mapping is the single combo value `antichess`.

The inherited orthodox `bench` and `speedtest` contracts are not valid for
this profile. `bench` is replaced by the frozen `ANTICHESS_BENCH_V1` corpus:
13 rules-focused positions, one thread, one-megabyte Hash, depth one through
eight, and the engineering-neutral evaluator. The depth-two reference is 737
nodes with canonical record digest
`d1be4e239ef3ab607a3806f61397e2b9d1a71f3b8429bc2c5cea904137862904`.
The verifier ignores elapsed time and NPS, repeats the exact search records,
checks evaluator restoration, and rejects incompatible parameters. `speedtest`
fails closed until the P7 search gate defines an Antichess workload.

## Consequences

- A correctness build, pair smoke, or terminal mate score is not Elo evidence.
- Future search work must introduce one audited hypothesis at a time and keep
  any refactor separate.
- Before enabling any inherited Stockfish heuristic, its Antichess legality,
  value perspective, history dependence, and make/undo behavior need focused
  fixtures and a new receipt.
- A later asynchronous, clock-managed search replaces this baseline only after
  its own correctness and deterministic-digest gates pass.
