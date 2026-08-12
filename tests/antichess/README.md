# Antichess correctness suite

[`fixtures/core-v1.json`](fixtures/core-v1.json) is the first frozen executable
contract for `LICHESS_ANTICHESS_V1`. It contains complete sorted legal-move
sets, exact terminal and history states, negative move and parser cases, and
the lila service-result matrix for one-sided cannot-win positions.

Expectations were produced outside the candidate engine. The valid-position
and move-set fields agree between the pinned scalachess authority and pinned
chessops reference. History, automatic results, and external result reasons
come from pinned scalachess and lila. The fixture document records chessops
limitations instead of using it as a proxy for service behavior.

Run the repository-only contract checks with:

```text
python tools/reference/verify_fixture_contract.py
```

With the exact chessops checkout from `RULES/AUTHORITY.lock.json` built under a
local reference cache, run the independent differential verifier with:

```text
node tools/reference/chessops/verify_fixtures.mjs \
  --chessops-root .reference-cache/chessops \
  --fixtures tests/antichess/fixtures/core-v1.json
```

`tools/reference/scalachess/ScalachessProbe.scala` is compiled only against the
exact external scalachess checkout. It has no candidate-engine dependency.

An exact referee and candidate-engine verifier still have to pass the same
contract. Until they do, upstream perft numbers and candidate search output are
engineering observations only and do not close P2/P4.
