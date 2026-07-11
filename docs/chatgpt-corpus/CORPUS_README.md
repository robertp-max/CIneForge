# CineForge ChatGPT Corpus

Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b`  
Generated at: `2026-07-11T19:38:25.5981047Z`

## Purpose

This corpus is a compact, durable, ChatGPT-readable map of the CineForge repository. It captures architecture, implementation status, Git state, tests, plans, risks, and the recommended next implementation task without copying the whole repository.

## Source

- Source repository path: `C:\AI\Git\CIneForge`
- Corpus worktree path: `C:\AI\Git\_worktrees\CIneForge-chatgpt-corpus`
- Source branch: `master`
- Source commit: `5ae274d69545d1c2a39406ec5de8a1bdb7ebc84b` (`Fix backend root status and complete next phase`)
- Source remote: `https://github.com/robertp-max/CIneForge.git`

## How ChatGPT Should Use This Corpus

Start with `CHATGPT_CONTEXT.md` for a fast orientation. Use `IMPLEMENTATION_MATRIX.md` to check what is implemented versus scaffolded. Use `SOURCE_DIGESTS.md` and `REPOSITORY_MAP.md` when selecting files for a task. Use `NEXT_ACTION_PROMPT.md` as the hardened next-task prompt unless a newer human instruction overrides it.

## Refresh Procedure

1. Do not switch the user's active branch.
2. Fetch origin.
3. Update the separate `chatgpt/corpus` worktree.
4. Regenerate only `docs/chatgpt-corpus/`.
5. Re-run safe tests without installing dependencies.
6. Review for secrets and large artifacts.
7. Commit with `docs: refresh CineForge ChatGPT corpus`.
8. Push `chatgpt/corpus`; do not merge it into `master` automatically.

## Limitations And Exclusions

- Excluded: `.env`, credentials, private keys, local databases, model binaries, generated media, `node_modules`, caches, large logs, generated assets, and untracked active-worktree handoff files.
- The active worktree was dirty during generation; that state is recorded in `GIT_STATE.md` but not included as source content.
- PostgreSQL-specific tests were blocked by unavailable local port `127.0.0.1:55432`.
- Frontend build/lint were blocked by missing `node_modules`; dependencies were not installed by design.

## Canonical Source-Of-Truth Rules

1. Current code at `5ae274d` is primary truth.
2. Tests are supporting evidence.
3. Newer status docs beat older plans only where they match code.
4. Older docs marked stale must not override implementation evidence.
5. Future ChatGPT sessions should verify Git state before acting.
