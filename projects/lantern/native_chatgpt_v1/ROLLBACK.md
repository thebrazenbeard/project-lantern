# Rollback

Rollback is Project-facing only and must not delete Lantern provider history.

To remove this native integration:
1. Remove the `PROJECT LANTERN NATIVE RUNTIME V1` addendum from the target Project instructions.
2. Remove the four `LANTERN_*_V1.md` Project files that came from this package.
3. Leave Project Lantern's Git history, Supabase schema, migrations, material, receipts, and provenance untouched.
4. Record that native integration was removed; do not claim the backend was rolled back.

If another Project file depends on these files, stop and resolve that dependency before removal.
