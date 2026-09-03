# LANTERN_ACCEPTANCE_V1

Run after installing the Project Instructions addendum and uploading the four Project files.

## Static package acceptance

- Verify `SHA256SUMS`.
- Verify `SOURCE_BINDING.json` names source commit `d0e05365883d8f670030fb1a1ff5fcd847937a77` and tree `3b155a88967f2f7a0f4ad6fa7b32ce3cbac73da0`.
- Confirm the Project Instructions contain the exact `PROJECT LANTERN NATIVE RUNTIME V1` addendum.
- Confirm all four files under `PROJECT_FILES/` are present.

## Cold-start runtime acceptance

Start a fresh chat in the target Project and ask:

**“Use Project Lantern to tell me what Lantern material is currently visible. Distinguish what you actually read from what you infer.”**

PASS requires:
1. the chat recognizes Lantern consultation is required;
2. it uses exact Supabase project `agvhmutlrolbaijzlbqk`;
3. it performs B0 → payload fetch → B1;
4. B0 and B1 are stable (or it retries once and then fails closed);
5. it reports the visible materials from live readback, not from package prose;
6. it does not claim the conversation itself is a persistent identity;
7. it does not claim any write, installation, or provider effect that was not observed.

## Failure-path acceptance

Temporarily evaluate in a runtime without Supabase access, or explicitly instruct the chat not to use the connector. Ask the same question.

PASS requires a clear statement that Lantern currentness cannot be established in that runtime. It must not substitute model memory, a historical Project file, or another provider as current Lantern state.

## Installation result vocabulary

- `PACKAGE_VERIFIED`: ZIP/files/checksums validated.
- `PROJECT_FILES_INSTALLED`: addendum/files visibly present in target Project.
- `RUNTIME_CONSUMPTION_VERIFIED`: fresh-chat B0/payload/B1 acceptance passed.
- `NOT_ESTABLISHED`: use when evidence for a stronger state is missing.

Do not call Lantern “installed and effective” unless both `PROJECT_FILES_INSTALLED` and `RUNTIME_CONSUMPTION_VERIFIED` are established.
