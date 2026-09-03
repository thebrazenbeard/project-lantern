# Project Lantern Native ChatGPT Integration V1 — Design

Date: 2026-09-02

## Goal

Deliver the missing user-facing Project Lantern endpoint as a reproducible ChatGPT Project installation package without modifying the already-green Lantern provider.

## Boundary

The native layer is a read-only operator/runtime contract. It binds a target ChatGPT Project to exact Lantern provider/source provenance, defines consultation triggers, performs a B0 → payload → B1 stability handshake, and fails closed when currentness cannot be established. A chat/session is treated as an ephemeral terminal; the package does not claim persistent private experience or make the chat itself the continuity store.

## Components

- Project Instructions addendum.
- Four Project files: runtime contract, operator handshake, read queries, acceptance.
- Installation/rollback docs.
- Source binding, manifest, checksums, install receipt template.
- Deterministic ZIP delivered to Patrick.

## Current source/provider binding

Git: `thebrazenbeard/project-lantern@d0e05365883d8f670030fb1a1ff5fcd847937a77` / tree `3b155a88967f2f7a0f4ad6fa7b32ce3cbac73da0`.
Provider: Supabase `agvhmutlrolbaijzlbqk` / project scope `PROJECT_LANTERN`.
Provider observation at build: 1 policy, 1 accepted profile, 3 grants, 2 materials, 2 receipts, 2 runtime-visible rows; migrations through `20260901180815_lantern_fix_plpgsql_alias_collision_v1`.

## Safety / authority

No Supabase mutation, merge/main write, credentials, live Project-file replacement, or automatic installation. Build, installation, runtime consumption, and provider effect remain distinct states. C-01/C-02 true multi-session timing remains a documented provider-verification limitation and does not block this package.
