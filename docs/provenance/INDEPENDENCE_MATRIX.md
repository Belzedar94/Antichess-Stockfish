# Rules evidence independence

| Role | Pinned implementation | Current status | May generate fixture expectations? |
| --- | --- | --- | --- |
| Normative authority | Lichess/scalachess `cbffc9d7...` plus lila `13895e58...` | PINNED | Yes, through cited behavior/tests |
| Independent reference | chessops `736c40ce...` | PINNED, NOT YET EXECUTED | Yes, after the harness is reproducible |
| Referee | Cute Chess `5e84232b...` plus an explicit claim-policy correction or adapter | BLOCKED | Yes, only after it independently passes the suite |
| Candidate | Fairy-Stockfish `c19b5f6c...` | SUBJECT UNDER TEST | Never |
| Diagnostic loader asset | `antichess-dd3cbe53cd4e.nnue` | LOCAL-ONLY | Never |

Agreement is resolved against pinned authority, not majority vote. The
reference and referee must not become two wrappers around the same underlying
rules core. Candidate results cannot be copied into expected fixtures.

Known non-independent tools:

- `pyffish` is a binding of Fairy-Stockfish and can only probe the candidate;
- Fairy-Stockfish perft counts are engineering regression evidence, not an
  independent rules oracle;
- the legacy network is an evaluator container, not a rules authority.
