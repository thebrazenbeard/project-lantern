# LANTERN_OPERATOR_HANDSHAKE_V1

Use this handshake when a fresh ChatGPT session needs Lantern.

1. **Session boundary.** Record mentally that the current chat is an ephemeral terminal. Do not claim uninterrupted hidden continuity.
2. **Target binding.** Confirm the available Supabase connector can read exact project `agvhmutlrolbaijzlbqk`. Do not substitute another Supabase project/provider.
3. **Source binding.** Package build source is `d0e05365883d8f670030fb1a1ff5fcd847937a77` / tree `3b155a88967f2f7a0f4ad6fa7b32ce3cbac73da0`. Treat this as package provenance, not proof the mutable source branch has not moved.
4. **B0 material cut.** Execute the connector-ready `LANTERN_MATERIAL_CUT_V1` from `LANTERN_READ_QUERIES_V1.md`.
5. **Material fetch.** Read `lantern_material.runtime_visible_v1` for project scope `PROJECT_LANTERN`. Cross-check every returned material ID + canonical digest + semantic key + source digest against B0 `exact_members`; counts and membership must match exactly.
6. **B1 material cut.** Execute the same cut again.
7. **Stability.** B0 and B1 must match exactly. If not, restart steps 4–7 once. A second mismatch => `UNKNOWN`.
8. **Use.** Only after a stable cut may Lantern material be used as current material evidence.
9. **Report ceiling.** Say what was actually established: package present, backend consulted, stable material cut obtained, and/or specific material used. Do not collapse these into “Lantern is installed/effective” unless the installation acceptance receipt also exists for this Project.

If the user asks for a current mutable GitHub state, fetch GitHub separately. Lantern material can reference a source commit but does not make a historical source binding current.
