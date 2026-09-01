# S3 Fairy-Stockfish same-network three-time-control panel

## Status

**ENGINE CAPABILITIES AND PANEL-INPUT CERTIFICATION CLOSED; FINAL STRENGTH
PREREGISTRATION NOT YET SEALED. No strength games have been run.**

Certification PR #12 was reviewed at exact head `5cd42637`, merged as
`3df08453`, and completed post-merge CI run `33474221364`. The winner tree is
identical to the merge tree, official Stockfish remains in ancestry, and the
Fairy-Stockfish comparator does not enter candidate ancestry.

The owner requires Antichess-Stockfish to beat the strongest available
Fairy-Stockfish comparator before Antichess NNUE V2 work begins. Both engines
must load the exact same legacy network bytes. This is a whole-engine strength
comparison; it cannot attribute any result to NNUE.

The readiness audit originally found no clock-responsive search and a
one-MiB Hash ceiling. Those two engine blockers are now closed by the reviewed
clocked-iterative and bounded TT512 hypotheses. The exact post-governance
candidate source is `d08da0c88b7b933eb3c94e6c10a91e0a04f9f769`; its
panel Windows binary is now reproducibly frozen, and the separately
preregistered input certification passed once. Running the panel before its
final strength preregistration, exact-head review, and merge closure would
still be invalid.

## Frozen identities already available

- Exact candidate source commit:
  `d08da0c88b7b933eb3c94e6c10a91e0a04f9f769`.
- Candidate Windows binary SHA-256:
  `5459225015a9734a3f0322b3fa4a9accdb74c5d3cb82a4efe371ae5715286213`.
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
dialect behavior and all 202 selected opening positions now agree exactly with
the candidate and `AC_REFEREE_V1` on legal move sets.

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

1. **CLOSED:** clock-responsive iterative search passed, merged, and completed
   post-merge CI.
2. **CLOSED:** bounded TT512 r2 passed its one-shot fixed-work rule, merged,
   and completed post-merge CI.
3. **CLOSED:** the v2 input certification ran once and passed all 56 focused
   positions, all 202 opening positions, positive and negative network probes,
   879 referee checks, and a two-game non-strength plumbing smoke.
4. **NEXT GATE:** freeze the final project-local strength runner, deterministic
   schedule, stopping formula, invalidation contract, time margins, and host
   lease under a separate immutable preregistration, then review and merge it
   before the first panel game.

Until blocker four closes through exact-head review, merge, and post-merge CI,
no VSTC, STC, LTC, Elo, OpenBench, or release claim is authorized by this
document.
