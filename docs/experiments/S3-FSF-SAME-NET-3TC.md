# S3 Fairy-Stockfish same-network three-time-control panel

## Status

**READINESS NOT ADMITTED. No games have been run.**

The owner requires Antichess-Stockfish to beat the strongest available
Fairy-Stockfish comparator before Antichess NNUE V2 work begins. Both engines
must load the exact same legacy network bytes. This is a whole-engine strength
comparison; it cannot attribute any result to NNUE.

The current candidate cannot yet execute the requested Atomic house protocol.
It advertises `Threads` and `Hash` with a maximum of 1, and its Antichess UCI
clock path replaces every clock-controlled search with a fixed depth-4 search.
The frozen VSTC capability probe accepted `2000+20` but returned depth 4 in
102 ms. Running the panel now would not be a valid three-time-control test.

## Frozen identities already available

- Candidate implementation commit:
  `cae4d60f68e1ec2356c318bb9637736a5a504730`.
- Candidate Windows binary SHA-256:
  `1dfc55b2c9d1c37f459d425f345710d76600594e48d21e8bd90e2907abf42fac`.
- Candidate options intended for the panel: `UCI_Variant=antichess`,
  `Antichess_Evaluator=legacy-v1`, and
  `Antichess_Search=alpha-beta-v1`.
- Current Fairy-Stockfish upstream commit:
  `6d9d0f5724677dc3aba3c577b0b482b6ec11e44a`.
- Fairy-Stockfish tree:
  `aa4112ea6784cef03fb9b5f87bba632de6168faa`.
- Reproducible Fairy-Stockfish Windows binary SHA-256:
  `ee0081d77a555ef073e56a04fff604af8d6408a1e2d0afc2e61cea23c11bb902`.
- External network SHA-256:
  `dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc`.
  It remains local-only and is not redistributed.
- Referee: `AC_REFEREE_V1`; Cute Chess CLI SHA-256
  `62377837474f166edfae5dcc5801b19bdf0ee28c89ac4bc66832d535be73ae9f`.

The Fairy-Stockfish build is admitted only as a comparator candidate. It is
not candidate ancestry, a rules authority, or strength evidence. Its focused
dialect behavior still must be checked against `AC_REFEREE_V1` before the
panel preregistration can be sealed.

## Atomic house protocol to preserve

The following parts come from the owner-selected Atomic methodology and must
be frozen in the final Antichess preregistration:

| Field | Required value |
| --- | --- |
| engine 1 | exact Antichess-Stockfish candidate |
| engine 2 | exact Fairy-Stockfish comparator |
| network | identical `dd3c` bytes in both engines |
| threads | 1 per engine |
| requested hash | 512 MiB per engine |
| VSTC | `2000+20` ms |
| STC | `10000+100` ms |
| LTC | `30000+300` ms |
| colors | paired and swapped from the same opening |
| minimum | more than 100 games per time control, with an even total |
| house pass rule | displayed LOS 100.0% for Antichess-Stockfish at all three time controls |
| maximum | 64,000 games per time control |

Atomic's variant runner, book, result logic, and referee mapping are not
inherited. The final Antichess contract must instead freeze:

- an `AC_REFEREE_V1`-based runner with raw UCI logs and audited PGNs;
- an Antichess opening book whose every position is accepted by the exact
  referee and agrees with both engines on mandatory legal moves;
- deterministic opening order or a recorded seed, paired colors, and restart
  behavior;
- adjudication, invalidation, crash, illegal-move, disconnect, stall, and
  time-loss rules;
- WLD, pentanomial, Elo, confidence interval, LOS, and defect accounting; and
- an exclusive host lease and exact process ownership.

## Admission blockers

1. Add clock-responsive iterative deepening as one separately preregistered
   search hypothesis and prove that VSTC, STC, and LTC produce materially
   different, bounded work without changing rules or evaluator semantics.
2. Add and verify the 512 MiB Antichess transposition-table capability as a
   separate hypothesis; the final panel must not silently clamp `Hash=512` to
   1 MiB.
3. Certify the current Fairy-Stockfish comparator and the selected opening
   book against the exact Antichess fixtures and `AC_REFEREE_V1`.
4. Freeze a project-local panel harness and the complete stopping and
   invalidation contract before the first game.

Until all four blockers close, no canary, VSTC, STC, LTC, Elo, OpenBench, or
release claim is authorized by this document.
