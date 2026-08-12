# Antichess correctness suite

This directory will contain the decisive `LICHESS_ANTICHESS_V1` fixtures and
their executable harnesses.

Fixture expectations must be produced outside the candidate engine and must
record agreement between the pinned authority, chessops reference, and an
independent referee. Every fixture includes a complete legal-move set, exact
terminal/claim state, the transition at which it takes effect, provenance, and
an aggregate suite digest.

Until those artifacts exist and pass, upstream perft numbers and candidate
search output are engineering observations only. They do not close P2/P4.
