# Installation — Vera Unbound

This package does not self-install.

1. Extract the ZIP.
2. Verify `SHA256SUMS`.
3. Open the Vera Unbound Project instructions and append the complete contents of `PROJECT_INSTRUCTIONS_ADDENDUM.md`. Preserve the Project's existing instructions; do not replace unrelated instructions.
4. Upload these four files to the Vera Unbound Project:
   - `PROJECT_FILES/LANTERN_RUNTIME_CONTRACT_V1.md`
   - `PROJECT_FILES/LANTERN_OPERATOR_HANDSHAKE_V1.md`
   - `PROJECT_FILES/LANTERN_READ_QUERIES_V1.md`
   - `PROJECT_FILES/LANTERN_ACCEPTANCE_V1.md`
5. Ensure the runtime has authorized read access to the Supabase connector. This package contains no credential and grants no provider permission.
6. Run `LANTERN_ACCEPTANCE_V1.md` in a fresh Project chat.
7. Record the result using `INSTALL_RECEIPT_TEMPLATE.json`.

Do not alter the Lantern Supabase provider merely to install this package. Provider mutation is outside this installation.
