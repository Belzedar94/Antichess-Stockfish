# Incident ledger

## INC-DIALECT-001 — Hidden Antichess insufficient-material rules

- **Symptom:** the public variant page documented the headline win conditions
  but not the executable implementation's automatic draw and one-sided
  cannot-win classifiers.
- **False inference:** no insufficient-material rule applied because orthodox
  mating material is irrelevant when the king is non-royal.
- **Cause:** discovery initially stopped at public prose instead of tracing
  `autoDraw`, `isInsufficientMaterial`, and the service result paths.
- **Prevention:** enumerate every terminal and service-result predicate from a
  pinned executable authority and require positive and near-negative fixtures.
- **Gate:** P2 and P4.

## INC-DIALECT-002 — Malformed en-passant text crossed a permissive wrapper

- **Symptom:** a low-level scalachess wrapper canonicalized `z9` to no
  en-passant square while chessops rejected it.
- **False inference:** every string accepted by the wrapper was valid public
  FEN.
- **Cause:** the wrapper assumed prevalidated transport text.
- **Prevention:** every project-owned boundary rejects malformed tokens before
  rules execution; valid but ineffective en-passant fields canonicalize to
  `-`.
- **Gate:** P2, P3, P4, P8, and P12.

## INC-BASELINE-001 — Legal-move conformance masked terminal drift

- **Symptom:** a historical candidate matched mandatory-capture legal sets but
  disagreed on repetition, move-count, material, and parser outcomes.
- **False inference:** a matching name, perft, and ordinary search smoke proved
  the exact Lichess profile.
- **Cause:** terminal, history, service, and parser semantics were not yet part
  of the baseline manifest.
- **Prevention:** freeze full legal, terminal, history, material-perspective,
  notation, and parser fixtures before implementation.
- **Gate:** P2 through P6.

## INC-SOURCE-001 — An unapproved source base advanced through correctness work

- **Symptom:** substantial work was performed on a Fairy-Stockfish-derived
  branch before the source-base decision had an explicit owner go.
- **False inference:** dialect fidelity and legacy-loader affinity were enough
  to select a production source base.
- **Cause:** source selection was treated as an engineering ranking instead of
  an owner-controlled scope decision.
- **Prevention:** P0 requires an immutable owner decision. A source-base no-go
  archives the lineage and allows only a hashed contract allowlist to cross.
- **Gate:** P0; the old lineage is `REJECTED_ENGINEERING`.

## INC-ORACLE-001 — Browser review slot timeout was not a review verdict

- **Symptom:** the first browser-only Pro review attempt exhausted its slot
  before producing a model response.
- **False inference:** the architecture was rejected or the review requirement
  was satisfied by the failed session.
- **Cause:** browser session availability, not model analysis or repository
  content.
- **Prevention:** preserve the failed session classification, retry once with a
  minimal non-secret bundle, verify requested/resolved model identity, and
  hash the completed transcript. Continue locally when review infrastructure
  remains unavailable, as owner-authorized.
- **Gate:** architecture decisions before P3, P8, P12, P15.

## INC-BUILD-001 — Host contention looked like a candidate compiler failure

- **Symptom:** the first parallel debug build terminated while GCC was
  compiling during an unrelated high-memory compiler workload on the host.
- **False inference:** the Antichess source or compiler was invalid.
- **Cause:** concurrent memory pressure caused the compiler process to fail;
  the source produced no relevant diagnostic.
- **Prevention:** inspect process ownership read-only, never terminate foreign
  work, wait for an uncontended window, retry once serially, and preserve both
  classifications. Require an explicit exclusive-host lease before timing
  measurements.
- **Gate:** P3 for correctness builds and P7/P14 for performance work.

## INC-BUILD-002 — The wrong MSYS2 wrapper hid a missing runtime dependency

- **Symptom:** invoking the build through a generic `bash.exe -lc` caused
  `cc1plus` to exit without a compiler diagnostic; the Windows status mapped to
  `0xC0000135`.
- **False inference:** a silent exit from `g++` proved a compiler or source
  failure.
- **Cause:** the wrapper did not establish the MinGW runtime DLL search path.
- **Prevention:** use `msys2_shell.cmd -defterm -no-start -mingw64` for the
  pinned Windows build and classify wrapper, process, log, and artifact
  evidence before assigning a compiler failure.
- **Gate:** P3 and P15.

## INC-TOOLCHAIN-001 — Requested sanitizers were unavailable locally

- **Symptom:** MinGW GCC had no ASan/UBSan runtime libraries, while the installed
  Clang executable itself failed with a Windows DLL entry-point error.
- **False inference:** a sanitizer command line or a failed wrapper invocation
  constituted sanitizer evidence.
- **Cause:** the local toolchain installation cannot execute a supported
  sanitizer build.
- **Prevention:** record the local gap, do not mark sanitizer checks green, and
  require a pinned Linux CI sanitizer job before P6.
- **Gate:** P6.

## INC-DIALECT-003 — Effective en passant escaped a physical-material draw

- **Symptom:** the candidate and the secondary chessops reference classified a
  blocked-pawn, opposite-bishop position as drawn even when the side to move
  had an effective en-passant capture.
- **False inference:** the physical piece placement alone determined the
  blocked-pawn material result.
- **Cause:** en-passant state is history-dependent and can make an otherwise
  blocked pawn capturable for one ply.
- **Prevention:** include canonical effective en passant in every material
  classifier and freeze paired positive/negative fixtures that differ only in
  that field. A reference with a declared material gap remains legality-only
  for this family.
- **Gate:** P2, P4, P8, and P12.

## INC-REFEREE-001 — A matching Cute Chess variant name hid result drift

- **Symptom:** vanilla Cute Chess generated compulsory Antichess captures but
  automatically ended games at threefold repetition and inherited incompatible
  material, timeout, and SAN behavior.
- **False inference:** the `antichess` board name and legal-move agreement were
  sufficient referee certification.
- **Cause:** board rules, match-service claims, `winPossible()`, and notation
  are separate code paths and were not versioned as one executable profile.
- **Prevention:** require the exact `AC_REFEREE_V1` base commit, patch hash,
  derived tree, source blobs, behavioral probe, notation fixtures, and raw UCI
  mapping. Production OpenBench remains unknown until its actual client and
  referee path pass the same evidence.
- **Gate:** P4, P7, P14, and P16.
