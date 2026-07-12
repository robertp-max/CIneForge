# ChatGPT corpus refresh

Run `scripts/refresh_chatgpt_corpus.ps1` explicitly after a meaningful,
verified implementation checkpoint. The script uses the dedicated
`chatgpt/corpus` branch and `C:\AI\Git\_worktrees\CIneForge-chatgpt-corpus`;
it never switches the active repository worktree.

The refresh resolves and records the source commit, regenerates only
`docs/chatgpt-corpus`, scans generated text for credential-like material,
skips commits when unchanged, and refuses to continue when the remote corpus
branch is ahead or divergent. Pushing is opt-in through `-Push`; force-push is
not implemented. There is no watcher or background task.
