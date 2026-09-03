# Project Lantern Native ChatGPT Integration V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build, validate, source-control, and deliver `PROJECT_LANTERN_CHATGPT_INSTALL_V1.zip`.

**Architecture:** Add a self-contained read-only native integration source directory on the isolated Lantern branch. The package installs one Project Instructions addendum plus four Project files and uses a B0/payload/B1 Supabase read handshake.

**Tech Stack:** Markdown, JSON, SHA-256, ZIP, Git/GitHub.

**Spec:** `docs/superpowers/specs/2026-09-02-lantern-native-chatgpt-integration-v1-design.md`

## Global Constraints

- Source base is exact `d0e05365883d8f670030fb1a1ff5fcd847937a77`.
- No Supabase mutation.
- No merge/main write.
- No live Project installation in this implementation.
- Build/install/runtime/effect states remain distinct.

---

### Task 1: Native package source

- [x] Define Project Instructions addendum.
- [x] Define runtime contract, operator handshake, read queries, and acceptance.
- [x] Define install/rollback evidence files.
- [x] Bind exact Git/provider provenance.

### Task 2: Package integrity

- [x] Generate `MANIFEST.json`.
- [x] Generate `SHA256SUMS`.
- [x] Validate required file set, JSON parseability, source binding, and checksums.
- [x] Build deterministic ZIP and verify extract-to-byte equivalence.

### Task 3: Git custody

- [ ] Re-read isolated branch prestate.
- [ ] Create one source commit containing design/plan plus unpacked package artifacts.
- [ ] Fast-forward `feature/lantern-native-chatgpt-integration-v1`.
- [ ] Read back commit/tree/files and compare against base.

### Task 4: Delivery

- [ ] Record exact branch/head/package digest and limitations on the Lantern issue/Chat Bus.
- [ ] Hand the verified ZIP to Patrick.
