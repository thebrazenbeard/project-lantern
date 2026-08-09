# Lantern Git-and-Markdown Control v1

Status: `FROZEN_BEFORE_IMPLEMENTATION_RESULTS`
Fixture: `LANTERN-FIXTURE-V1`

This control uses only a disciplined directory of immutable Markdown records and a Git history. It does not use Lantern code.

## Capture procedure

1. Create one Markdown file per SourceSnapshot, Claim, Assessment, Decision, Link, and StateEvent.
2. Never edit an existing record file. A revision creates a new file naming the predecessor record ID.
3. Maintain `CURRENT.md` by hand with the current lineage head for each lineage key.
4. Maintain `LINKS.md` by hand with typed source and target record IDs.
5. When SourceSnapshot B supersedes A, search `LINKS.md` for direct `DEPENDS_ON` targets equal to A and append one `REVIEW_REQUIRED` row for each direct active Assessment or Decision. Do not recurse.
6. Commit all changes with Git.

## Reconstruction procedure

Answer the five questions in `expected-answers-v1.json` using only the Markdown files and Git history. Record files inspected and elapsed operator time.

## Fixed IDs

- SourceSnapshot A: `019fcdb7-c668-7e7d-9ce4-7831e099e77e`
- SourceSnapshot B: `019fcdb7-f548-7fb4-9345-7ee26a4f5b27`
- selected Claim: `019fcdb7-ca50-79b0-aa8c-ef4da1562f18`
- opposed Claim: `019fcdb7-ce38-7115-a37a-7d2550880f2d`
- Assessment: `019fcdb7-d608-7702-8f7a-02989db85066`
- Decision: `019fcdb7-d9f0-7ab8-b5d5-8a6aa3b5742d`

## Control limitations

The control is intentionally disciplined rather than deliberately incompetent. Manual projection and review-trigger maintenance count toward operator time because they are part of preserving equivalent reliability.
