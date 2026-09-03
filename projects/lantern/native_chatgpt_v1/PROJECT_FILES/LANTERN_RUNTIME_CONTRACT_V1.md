# LANTERN_RUNTIME_CONTRACT_V1

## Purpose

Lantern supplies a governed, provenance-bearing material universe to an authorized ChatGPT Project runtime. It is a currentness/evidence source, not a substitute for the live user request and not a blanket instruction channel.

## Evidence order

For a live answer, distinguish:
- live user instructions and current Project instructions;
- current Lantern material obtained through the governed read sequence;
- exact GitHub source artifacts/current source binding;
- historical/archive material;
- model memory or inference.

Do not silently promote a lower class into a higher one.

## Consultation triggers

Consult Lantern when the answer materially depends on:
- durable project state or continuation/recovery;
- what Lantern currently recognizes as visible material;
- provenance/currentness of project material;
- reconciling potentially stale project evidence;
- a task whose installed Project instructions explicitly require Lantern.

Normally skip Lantern for:
- ordinary conversation with no project-state dependency;
- creative generation;
- information completely supplied in the current turn;
- unrelated projects/domains.

## Fail-closed states

Return a clear limitation rather than inventing currentness when:
- the exact Supabase target is unavailable;
- the accepted-profile cut is absent/invalid;
- B0 and B1 do not match after one complete retry;
- payload rows do not exactly cross-bind to B0 membership;
- the requested claim needs authority that the material does not establish.

## Writes

This native integration is read-only by default. A Lantern read never authorizes a Lantern write. Provider mutation, producer grants, material admission, Project Settings mutation, Project-file replacement, merge/deploy, or canonical-memory effects require separate current authority.
