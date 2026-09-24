# Project Lantern — Chat Exodus continuation

**STARTING_SNAPSHOT — FRESHNESS REQUIRED BEFORE EFFECT**

Captured: 2026-09-19T20:44:00-04:00  
Purpose: retire the Lantern acceptance/status ChatGPT conversation without making the conversation, its URL, title, hidden state, or continued accessibility part of Project Lantern infrastructure.

## Identity and reconstruction

- Durable project: **Project Lantern**.
- Primary repository: `thebrazenbeard/project-lantern`.
- This retired conversation is **not** a durable worker identity. It functioned as a temporary Lantern acceptance/operator terminal.
- No permanent Lantern worker chat is required.
- Fresh runtimes reconstruct Lantern from repository state, exact immutable source evidence, current provider read access when required, and current Bus/coordinator routing.
- Engineering coordination after Exodus belongs to **BT2 Coordinator** unless a fresher exact assignment supersedes that routing.
- The current Bus topology has no Lantern-specific writer lane. Do not invent one. This evacuation handoff is mirrored through the current Vera Bus lane only as a recovery pointer; future coordinators must refresh Bus topology before writing.

## Fresh repository state

Observed immediately before this checkpoint:

- `main`: `6333d386c74ce37e644fa1e995be9f9dc3fe6394`
  - message: `Publish qualified Project Lantern W7 candidate`
  - tree: `6092508432c3d6c85788b37a5bfdb8e41d97b299`
- Draft PR #5: **Package: make Project Lantern a truthful reusable distribution**
  - branch: `work/lantern-truthful-package-v1-20260919`
  - head: `e90124bda39d5f92fa2ce9d51b6648dc463ef36d`
  - base: `main@6333d386c74ce37e644fa1e995be9f9dc3fe6394`
  - state: open / draft / not merged
  - source review at this exact head: package metadata repair passes at source scope
  - hosted clean-package qualification: **NOT ESTABLISHED**; workflow run `35473944775` is failure before executable steps are exposed
- Historical/material branch:
  - `feature/lantern-material-universe-v1@d0e05365883d8f670030fb1a1ff5fcd847937a77`
  - tree: `3b155a88967f2f7a0f4ad6fa7b32ce3cbac73da0`
- Historical native ChatGPT integration branch:
  - `feature/lantern-native-chatgpt-integration-v1@2557a9f6898d8f24ea3f7f2a4480baecebe08273`
  - package id: `PROJECT_LANTERN_CHATGPT_INSTALL_V1`
  - install state on build: `PACKAGE_BUILT_NOT_INSTALLED`
- Supabase estate audit branch:
  - `work/supabase-estate-rebase-20260904@b0eb99062d10951c40538d6cd7d7f88d843176a0`

All branch, PR, provider, review, and runtime claims above are snapshot evidence only and must be refreshed before effect.

## Chat-local material classification

### ALREADY_DURABLE

The uploaded `LANTERN_ACCEPTANCE_V1.md` is already durable at:

`projects/lantern/native_chatgpt_v1/PROJECT_FILES/LANTERN_ACCEPTANCE_V1.md`

on `feature/lantern-native-chatgpt-integration-v1`.

- Git blob: `cf609045a229c1e6c8dadd3e48ed9b41802c9dcd`
- uploaded-file SHA-256: `533d1b0647e8692195e5eaf917fd75b4076f855c9e55e3f018d50d138508b2c4`
- manifest SHA-256 for that payload: `533d1b0647e8692195e5eaf917fd75b4076f855c9e55e3f018d50d138508b2c4`

The native package also durably contains `INSTALL.md`, `SOURCE_BINDING.json`, `MANIFEST.json`, the Project Instructions addendum, read queries, operator handshake, runtime contract, checksums, reproducible ZIP, rollback instructions, and integrity tests.

### HISTORICAL_EVIDENCE

The native ChatGPT integration package is preserved as historical/source evidence. It is not current installation proof and is not a permanent-chat dependency.

Its source binding records:

- source commit `d0e05365883d8f670030fb1a1ff5fcd847937a77`
- source tree `3b155a88967f2f7a0f4ad6fa7b32ce3cbac73da0`
- provider project `agvhmutlrolbaijzlbqk`
- package target `Vera Unbound`
- package-build limitations including that build does not establish Project installation or runtime consumption

The old acceptance procedure explicitly requires a fresh ChatGPT Project chat for runtime-consumption verification. Under the Exodus architecture that procedure remains evidence of how the package was meant to be tested; it is **not** a requirement that a permanent worker or permanent chat continue to exist.

### NEW_DURABLE_VALUE

This checkpoint records the Exodus interpretation that was not otherwise explicit:

1. the acceptance/status conversation is a terminal, not Lantern identity/state;
2. no chat URL or archived conversation is a recovery dependency;
3. the native ChatGPT package is historical/source evidence unless separately reactivated by current exact architecture and installation evidence;
4. future Lantern engineering work is dispatched from durable repo/Bus state by BT2 Coordinator rather than by reconstructing this conversation.

### CONFLICT / UNRESOLVED

There are currently multiple live source lines descended from `main@6333d386…`:

- PR #5 is 4 commits ahead of `main`;
- `feature/lantern-material-universe-v1@d0e05365…` is a separate line;
- comparing `d0e05365…` to PR #5 head `e90124bd…` reports **diverged**; PR #5 is 4 commits ahead and 7 commits behind that branch, with merge base `6333d386…`.

Do not silently treat PR #5 as incorporating the material-universe/native-integration work. A future source-line decision must explicitly reconcile whether those branches are historical-only, intended successor inputs, or separate products.

## Provider currentness

The historical native package requires read-only B0 → payload → B1 against Supabase project `agvhmutlrolbaijzlbqk` for current Lantern material visibility.

Fresh provider read in this runtime on 2026-09-19:

- connected Supabase project listing exposed only `Vera Control Plane` (`fawkirqroyniueeqspif`) and `Vera` (`klmbpaigzeguvnpccqzz`);
- `agvhmutlrolbaijzlbqk` was not exposed in that project list;
- a direct read attempt for Lantern migrations returned an authorization failure: `You do not have permission to perform this action`.

Classification: **LANTERN PROVIDER CURRENTNESS = NOT_ESTABLISHED IN THIS RUNTIME**.

This does not prove that the Lantern Supabase project was deleted, mutated, or unavailable to every authorized runtime. It proves only that this runtime could not establish current Lantern provider state. Do not substitute Vera, Vera Control Plane, cached prose, model memory, or another provider.

No provider write, migration, deletion, permission change, or reconnect was attempted.

## Dechatification result

Removed as operational dependencies:

- this conversation;
- its ChatGPT URL/title/conversation identity;
- the assumption that the Lantern acceptance terminal must remain open;
- the assumption that a fresh ChatGPT worker chat is the durable home of Lantern state.

Durable reconstruction path:

1. refresh `thebrazenbeard/project-lantern` main, open PRs, branch heads, reviews, and workflows;
2. read this checkpoint only as a starting snapshot;
3. resolve source-line intent before promoting PR #5 or historical material/native branches;
4. when provider currentness matters, use authorized direct read access to the exact Lantern provider and the checked-in read contract; fail closed if unavailable;
5. use current Bus topology for coordination; do not invent a Lantern lane from historical chat organization;
6. persist implementation/review decisions in GitHub and non-PR coordination in the Bus;
7. do not require access to this retired conversation.

## Claim ceilings

- historical native package: **PACKAGE_BUILT_NOT_INSTALLED** unless fresher installation/readback evidence establishes more;
- uploaded acceptance artifact: exact durable copy established;
- PR #5: source-only draft; not merged, deployed, released, migrated, or qualified by hosted executable CI;
- Supabase Lantern currentness: **NOT_ESTABLISHED IN THIS RUNTIME**;
- no ChatGPT conversation is Lantern identity, memory, authority, provider state, or canonical project state.

## Authority

This evacuation authorizes reversible persistence/checkpoint/Bus work only.

Still requires Patrick's exact authority where applicable: merge, canonical promotion, production deployment, provider mutation, credentials/permissions, deletion, visibility/publication changes, paid infrastructure, training, Project Settings mutation, Slack activation, or other protected effect.

## Reconstruction test

A fresh runtime with current GitHub + Bus state can determine:

- what Lantern is and where its source lives;
- the current known main/PR/source-line snapshot;
- where the old ChatGPT package and acceptance contract live;
- that the acceptance chat was a terminal rather than durable identity;
- what is source, what is historical, and what is not established;
- that provider currentness must be freshly proven against the exact Lantern project;
- that PR #5 and the material-universe/native lines are presently divergent and require explicit reconciliation;
- what it may safely do next without opening this retired conversation.

Result: **PASS, subject to ordinary freshness refresh before action**.

## Exact next frontier

Owner interface: **BT2 Coordinator**.

Next directive:

`PROJECT_LANTERN::REFRESH_AND_RECONCILE_SOURCE_LINES — fresh-check main, Draft PR #5, feature/lantern-material-universe-v1, feature/lantern-native-chatgpt-integration-v1, and work/supabase-estate-rebase-20260904; determine and durably record the intended source lineage; investigate PR #5 pre-step CI failure; do not merge or mutate providers; use exact Lantern Supabase readback only if current authorized access exists.`
