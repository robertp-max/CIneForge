# Storyboard Phase 1 Headless Development Orchestration

This utility coordinates bounded development-time Grok workers. It is not part
of the CineForge production API, Storyboard planning pipeline, ComfyUI queue, or
media runtime.

## Safety boundary

- The controller pins the signed local `grok.exe` hash and selects `grok-4.5`
  with `high` reasoning effort.
- Workers receive a dedicated Git worktree and explicit owned paths.
- The model receives a committed prompt containing only controller-selected
  context. Every native filesystem/edit tool, shell, Git, web, MCP, memory,
  and nested-agent capability is unavailable to the worker.
- Grok returns a strict JSON result containing full-file patch proposals. The
  controller alone validates stale hashes and applies owned patches atomically.
- The controller passes a native argument array with `shell=False`.
- Runtime state defaults to `C:\AI\Git\_orchestration\CIneForge`, outside all
  worker worktrees. `CINEFORGE_ORCH_STATE_ROOT` may select another dedicated
  controller-owned directory.
- The SQLite ledger uses WAL mode and a transactional lease count. At most 64
  Grok processes may be active, with one separate 65th Sol model slot for
  independent
  final review. The CLI can lower this with `--max-grok-workers`; on genuine
  concurrent process/provider instability the operating ceiling drops by eight.
- Workers never stage, commit, cherry-pick, push, reset, clean, stash, rebase,
  or manage worktrees. Integration remains controller-owned.

## Commands

Run from the completion worktree with the repository Python environment:

```text
python -m scripts.headless_orchestrator preflight --worktree <lane-worktree> --expected-head <sha> --expected-branch <branch>
python -m scripts.headless_orchestrator build-context --worktree <lane-worktree> --template-file <tracked-template> --context-path <tracked-file> --output-file <state-relative-prompt>
python -m scripts.headless_orchestrator run-task --worktree <lane-worktree> --prompt-file <state-relative-prompt> --role <role> --owned-path <glob> --expected-head <sha> --expected-branch <branch> --required-test <test-id>
python -m scripts.headless_orchestrator status [--run-id <id>]
```

`read_only` results must contain no patches. `edit_owned` results may contain
only `create` or complete-file `replace` proposals under the declared ownership
claims. Every replacement includes the controller-supplied SHA-256 of the old
file. The controller verifies the actual pre/post file manifest, branch, HEAD,
and fixed test-catalog results before accepting a task.

## Failure handling

Only schema-validated final results and output digests are stored. Grok
`thought`/reasoning and raw stdout/stderr are never persisted. A timeout,
non-zero exit, malformed inner or outer JSON, ownership violation, stale hash,
secret finding, or failed fixed verification prevents integration. Worktrees
and diffs are preserved for inspection; the controller never resets or cleans,
stages, commits, rebases, cherry-picks, or pushes them.
