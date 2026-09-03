# Installation — Vera Unbound

This package does not self-install.

1. Extract the ZIP.
2. Verify `SHA256SUMS`.
3. Capture the exact current Vera Unbound Project Instructions before editing. Compute the exact Unicode character count of the complete post-merge artifact: current instructions + intended separator + the exact contents of `PROJECT_INSTRUCTIONS_ADDENDUM.md`. The currently observed native Project Instructions ceiling is 8,000 characters. If the combined artifact would exceed 8,000, STOP and redesign/shorten deliberately; do not truncate, silently replace unrelated instructions, or assume the addendum fits. If it fits, append the complete addendum while preserving the existing instructions.
4. Read back the exact merged Project Instructions and record its character count.
5. Upload these four files to the Vera Unbound Project:
   - `PROJECT_FILES/LANTERN_RUNTIME_CONTRACT_V1.md`
   - `PROJECT_FILES/LANTERN_OPERATOR_HANDSHAKE_V1.md`
   - `PROJECT_FILES/LANTERN_READ_QUERIES_V1.md`
   - `PROJECT_FILES/LANTERN_ACCEPTANCE_V1.md`
6. Ensure the runtime has authorized read access to the Supabase connector. This package contains no credential and grants no provider permission.
7. Run `LANTERN_ACCEPTANCE_V1.md` in a fresh Project chat.
8. Record the result using `INSTALL_RECEIPT_TEMPLATE.json`.

Do not alter the Lantern Supabase provider merely to install this package. Provider mutation is outside this installation.
