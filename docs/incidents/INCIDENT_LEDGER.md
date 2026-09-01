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

## INC-BENCH-001 — The inherited Stockfish bench was not an Antichess digest

- **Symptom:** the official 51-position bench requested the absent
  `UCI_Chess960` option and then terminated on orthodox move `g2g4`, which was
  illegal because a mandatory Antichess capture existed.
- **False inference:** a deterministic upstream Stockfish node count was a
  valid digest for the derived Antichess candidate.
- **Cause:** the inherited positions, move sequences, options, and workload
  encode orthodox chess assumptions.
- **Prevention:** replace the inherited command with the frozen
  `ANTICHESS_BENCH_V1` rules corpus, verify exact search records twice, ignore
  timing fields, reject incompatible arguments, and keep `speedtest` disabled
  until a P7 workload is preregistered.
- **Gate:** P3, P6, P7, and P14.

## INC-REFEREE-002 — A base checkout was passed where a patched worktree was required

- **Symptom:** the referee verifier reported `patched source drift:
  CMakeLists.txt` even though the frozen patch and derived tree were unchanged.
- **False inference:** the built referee or its source worktree had drifted.
- **Cause:** the caller supplied the pristine Cute Chess base checkout to an
  argument that intentionally verifies the patched worktree at the same base
  commit.
- **Prevention:** distinguish `base_root` from `patched_root` in runbooks and
  wrappers, verify the caller path before blob comparisons, and preserve the
  first failure classification. A corrected run must still reconstruct the
  patch from the base and verify every derived blob and behavior.
- **Gate:** P4, P6, and P15.

## INC-CI-001 — A transactional network load exceeded the Linux stack guard

- **Symptom:** the first official Linux release build failed under `-Werror`
  because `LegacyNetwork::load()` used 143,024 bytes of stack, above the
  inherited 128,000-byte compiler guard.
- **False inference:** a successful Windows build and loader test proved the
  temporary load path was portable and safe.
- **Cause:** the fail-closed transaction constructed all eight fixed layer
  stacks in a local `LegacyNetwork` object before committing the load.
- **Prevention:** keep the transaction but allocate its temporary candidate on
  the heap; retain the Linux stack guard and repeat loader mutation, exact
  evaluator parity, and clean-build evidence after the change.
- **Gate:** P3, P5, P6, and P15.

## INC-SEARCH-001 — A depth horizon discarded an available repetition claim

- **Symptom:** from a seven-ply reversible history, the only searched move
  created the third occurrence at depth zero. The exact baseline reported
  `cp +241` for the parent even though the child could claim a draw; the
  pinned legacy evaluator's child value was `-937`.
- **False inference:** exercising repetition claims above the horizon with the
  neutral evaluator proved that every claimable node had a zero-valued virtual
  option.
- **Cause:** the depth-zero return preceded construction of the claim option,
  so a negative legacy leaf value could replace an immediately available draw.
- **Prevention:** apply terminal and automatic-draw precedence first, evaluate
  the leaf, then floor a claimable leaf at zero. Freeze a legacy-network
  history fixture that reaches its third occurrence exactly at the horizon.
- **Gate:** P4, P6, P7, P13, and P14.

## INC-REVIEW-002 — Browser model-selector drift prevented the P7 review

- **Symptom:** the dry run resolved the requested browser review and eight
  attachments, but the live run failed before prompt submission because the
  selector no longer exposed the requested `Pro` option.
- **False inference:** a successful dry run or an acquired browser slot proved
  that the requested review model was available.
- **Cause:** the live product selector exposed a different model set than the
  requested exact model mapping.
- **Prevention:** preserve the failed session metadata and output, record that
  no verdict exists, never substitute another model silently, and continue
  only under an explicit owner waiver.
- **Gate:** P7, P14, and P15.

## INC-STRENGTH-001 — A fixed-depth correctness search could not execute the 3-TC protocol

- **Symptom:** the candidate accepted the Atomic VSTC clock command
  `2000+20` but returned its hard-coded depth-4 result in 102 ms; it also
  advertised `Hash` with a maximum of 1 while the selected protocol requires
  512 MiB.
- **False inference:** an official-Stockfish source lineage plus a successful
  alpha-beta fixed-work gate meant the candidate already had production
  Stockfish time management and transposition-table search.
- **Cause:** P7 intentionally isolated plain alpha-beta inside the correctness
  path. `Engine::go()` maps clock searches to depth 4, caps depth at 8, and the
  experiment explicitly excluded transposition-table cutoffs.
- **Prevention:** add clock-responsive iterative deepening and 512 MiB
  transposition-table capability as separate preregistered hypotheses, verify
  effective UCI settings and work scaling, and reject any strength launch that
  silently clamps settings or ignores its clocks.
- **Gate:** P7, P14, and P15.

## INC-REVIEW-003 — The GitHub review record was persisted after merge

- **Symptom:** pull request #8 was merged after its diff had been inspected and
  all official checks had passed, but before the no-blocking-findings review
  was submitted to GitHub. The review was persisted 57 seconds after merge.
- **False inference:** completing the local review and observing an empty
  review/comment queue was equivalent to freezing a review receipt before the
  merge mutation.
- **Cause:** the merge guard checked the exact head, mergeability, comments,
  and CI conclusions but did not require a non-null review identifier.
- **Prevention:** add the persisted review ID and submitted-at timestamp to the
  pre-merge checklist, and reject the merge command unless that review targets
  the exact head commit. If the record is late, disclose the ordering and close
  it in a separate post-merge governance addendum; never backdate it.
- **Gate:** P7, P14, and P15.

## INC-SEARCH-002 — An ordered history key eliminated true transpositions

- **Symptom:** the frozen TT512 v1 design required every reversible state key
  in newest-to-oldest order while also requiring useful TT hits, cutoffs, and
  at least 15% aggregate node reduction.
- **False inference:** a history-complete key could remain fully path-specific
  and still recognize ordinary transpositions reached through different move
  orders.
- **Cause:** two paths that form a transposition necessarily have different
  intermediate ordered histories. Hashing that complete order deliberately
  gives them different TT keys, so useful reuse can occur only on an identical
  path or through an accidental collision.
- **Prevention:** before implementation, prove both semantic sufficiency and
  reuse equivalence for every proposed context key. Bound any deliberate
  history abstraction by remaining search depth, freeze the proof and negative
  fixtures in a new preregistration, and reject an internally contradictory
  contract without compiling or consuming its candidate attempt.
- **Gate:** P7, P14, and P15.

## INC-BUILD-003 — A command-line flag replaced the official build flags

- **Symptom:** the first TT512-r2 wrapper invocation compiled with only
  `-Werror`; the normal optimization, architecture, language, and link-time
  optimization flags were absent from the emitted commands.
- **False inference:** adding `CXXFLAGS=-Werror` on the Make command line would
  append a diagnostic policy to the pinned release configuration.
- **Cause:** GNU Make command-line variable precedence replaced the Makefile's
  complete `CXXFLAGS` value instead of extending it.
- **Prevention:** use the supported `EXTRACXXFLAGS` and `EXTRALDFLAGS` extension
  variables, inspect the first emitted compiler and linker commands before
  admitting a build, and abort before producing or comparing a candidate when
  the pinned flags are absent.
- **Gate:** P3, P7, P14, and P15.

## INC-BUILD-004 — A repository-local detached worktree exceeded the Windows path limit

- **Symptom:** `git worktree add` failed before checkout while materializing
  long receipt filenames under a deeply nested `.local/worktrees` path. No
  compiler process started.
- **False inference:** keeping an isolated worktree inside the canonical
  repository automatically made its Windows path safe.
- **Cause:** the canonical repository path plus the proposed worktree suffix
  left insufficient path budget for tracked long filenames.
- **Prevention:** calculate or probe checkout path budget before a clean build,
  use an explicit short detached-worktree root when required, check every
  native Git exit code before continuing, and preserve checkout failures
  separately from compiler evidence.
- **Gate:** P3, P14, and P15.

## INC-S3-002 — A missing-network probe bypassed Fairy-Stockfish's variant selector

- **Symptom:** the first S3 certification stopped when the comparator accepted
  `missing-fsf-network.nnue`, announced classical evaluation, and returned a
  best move. No legal-set audit or game ran.
- **False inference:** any nonexistent `.nnue` path exercised the comparator's
  required-network failure path.
- **Cause:** Fairy-Stockfish first selects a variant network by matching the
  filename against `antichess` or its configured alias. The synthetic basename
  matched neither, so NNUE was intentionally deselected before file loading.
- **Prevention:** negative assets must preserve every routing predicate of the
  positive asset and mutate only the condition under test. For this comparator,
  the nonexistent basename must retain the `antichess` selector before a
  fail-closed load assertion is meaningful.
- **Gate:** P5, P14, and P15.

## INC-S3-003 — Two Windows host names disagreed at authorization validation

- **Symptom:** the first final authorization was rejected before runner
  execution because its host was `DESKTOP-XD38UAF`, while the frozen runner
  resolved `DESKTOP-OS8DSOT`. No output root or strength game was created.
- **False inference:** either the host changed or a matching Windows
  `COMPUTERNAME` value was sufficient for every runtime identity check.
- **Cause:** the authorization used the Windows environment/CIM alias, while
  the runner's normative CPython 3.12 `platform.node()` source returned a
  different name for the same machine.
- **Prevention:** derive authorization and lease host identity from the same
  pinned runtime used by the runner, record other host names only as aliases,
  and require a dry validation before any engine or output creation.
- **Gate:** P7, P14, and P15.

## INC-S3-004 — A PSReadLine rendering failure did not prove launch failure

- **Symptom:** submitting the long frozen runner command caused repeated
  `ArgumentOutOfRangeException` failures while PSReadLine redrew the prompt.
- **False inference:** a corrupted interactive prompt meant the command had
  not executed and could safely be submitted again.
- **Cause:** PSReadLine's display layer failed after PowerShell had accepted the
  command; the runner and its owned Cute Chess tree were already active and
  writing pair evidence.
- **Prevention:** after any ambiguous wrapper or terminal failure, inspect the
  create-once output root, exact process tree, lease, and ledger before retrying.
  Prefer a short noninteractive wrapper for long frozen invocations and never
  duplicate a command while any owned evidence or process exists.
- **Gate:** P7, P14, and P16.

## INC-STRENGTH-002 — Source freshness and specialization did not imply strength

- **Symptom:** with identical `dd3c` network bytes, Hash 512, one thread, the
  same openings, and the certified referee, the candidate scored 1 win and 101
  losses at VSTC and hit the preregistered 0.0% loss gate.
- **False inference:** starting from current official Stockfish and removing
  multi-variant overhead made a win over Fairy-Stockfish likely before the
  dedicated search had comparable strength machinery.
- **Cause:** source ancestry and specialization were mistaken for effective
  search architecture. The candidate's deliberately isolated alpha-beta,
  iterative-deepening, and bounded-TT work had proved correctness, scaling, and
  fixed-work reduction, not whole-engine strength. The match does not establish
  which individual search component caused the gap.
- **Prevention:** keep correctness, capability, speed, and strength evidence
  separate; preregister whole-engine gates; reject failed candidates without
  retuning; and admit a future panel only after one structural hypothesis at a
  time passes independent engineering fixtures and untouched validation.
- **Gate:** P7, P14, and P15.
