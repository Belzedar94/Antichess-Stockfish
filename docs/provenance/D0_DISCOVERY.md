# D0 discovery

The project owner authorized both `LICHESS_ANTICHESS_V1` and creation of the
public repository `Belzedar94/Antichess-Stockfish` on 2026-08-12.

## Repository boundary

- The expected root did not exist before bootstrap.
- The surrounding directory was a normative document kit, not a Git worktree;
  it was not initialized or overwritten.
- No duplicate local worktree or existing GitHub repository with this name was
  found.
- `Belzedar94` already owned the separate GitHub fork
  `Belzedar94/Fairy-Stockfish`, so this repository was created as an independent
  derivative while preserving the full upstream commit ancestry.
- `main` was first pushed at pristine upstream commit
  `c19b5f6c66894fdb0e88d0dd100e3885f744760a`.
- `upstream-fairy-stockfish-c19b5f6c` is an annotated base tag pointing to that
  commit. No upstream branch or tag set was mirrored.
- `origin` is `Belzedar94/Antichess-Stockfish`; `upstream` is
  `fairy-stockfish/Fairy-Stockfish`.

## Portfolio boundary

| Item | Assigned value |
| --- | --- |
| Project ID | `antichess-stockfish` |
| Rules profile | `LICHESS_ANTICHESS_V1` |
| Branch namespace | `antichess/*` after bootstrap |
| Campaign prefix | `ANTICHESS-` |
| Local cache | `.local/` and `.reference-cache/`, both untracked |
| Ports | none assigned |
| CPU/GPU lease | none assigned |
| OpenBench tests | none authorized |

Foreign projects, processes, workers, caches, books, networks, referees, and
campaign IDs are not inherited. An idle device or missing process is not a
handoff.

## Operational observations

The only official OpenBench URL is `https://belzedar.duckdns.org`. At the D0
snapshot it returned HTTP 200, but its pinned production code had no Antichess
worker mapping or versioned Antichess contract. Official workload submission
therefore remains abort-only.

A user-managed T24 worker was observed earlier during discovery and was not
touched. A later targeted read-only observation did not find the previous PID
or another command containing the production URL. The project neither stopped
nor restarted it; disappearance is not interpreted as authorization to claim
its resources.

## Architecture review

An independent advisory review returned a conditional GO for source/bootstrap
and a hard NO-GO for strength or official science until the executable
profile, independent roles, fixtures, clean builds, sanitizers, and
deterministic baseline are closed. Review evidence is retained in the private
operational record rather than the public repository.

The machine-readable receipt is
[`receipts/D0_DISCOVERY/2026-08-12T142712Z.json`](../../receipts/D0_DISCOVERY/2026-08-12T142712Z.json).
