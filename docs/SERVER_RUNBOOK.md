# University H100 server runbook

## Verified endpoint and capacity

- SSH: `wangpeng@127.0.0.1`, port `1022`
- Required identity: hostname `kemove-Rack-Server`, user `wangpeng`
- Raw/canonical proposal: `/private_nas/wangpeng/cognition-and-consciousness`
- Fast active work proposal: `/data1/wangpeng/cognition-and-consciousness-work`
- Restartable work proposal: `/data2/wangpeng/cognition-and-consciousness-work`
- Scheduler: no Slurm; use `tmux`

The root paths above remain proposals until the owner confirms them. Do not create alternate roots by guesswork.

## First deployment

1. Verify `hostname` and `id -un` in the same SSH session used for writes.
2. Run `scripts/server/bootstrap.sh --confirm-roots` from the immutable source release.
3. Confirm `conf/server_h100.yaml` reports `roots_status=owner_confirmed`.
4. Run `scripts/server/preflight.sh`; inspect the JSON report.
5. Create the commit-specific Python environment with `scripts/server/create_environment.sh <commit>`.
6. Queue P01, then P02:

```bash
scripts/server/queue_phase.sh P01
scripts/server/queue_phase.sh P02
scripts/server/status.sh
```

No password belongs in these commands. The local SSH password is entered only at an interactive prompt.

## Layout

```text
canonical_root/
  source/releases/<git-commit>/
  data/raw/<family>/<snapshot>/
  manifests/generated/
  logs/<phase>/<run-id>/
  run_state/<phase>/
  provenance/
  quarantine/
fast_root/
  stage/<family>/<subject-or-run>/
  tmp/
restart_root/
  derivatives/<family>/
  checkpoints/<phase>/
```

Source releases are content-addressed and not edited in place. Raw archives are retained. Extraction targets are separate. Corrupt or structurally unsafe downloads move to `quarantine`; nothing is automatically deleted.

## Monitoring and recovery

```bash
tmux ls
tmux attach -t factorcon-P02
scripts/server/status.sh
tail -n 100 /private_nas/wangpeng/cognition-and-consciousness/logs/P02/latest.log
```

Downloaders use `.part` files and resume with HTTP Range when supported. A file becomes complete only after expected-size and available upstream hash checks pass; a local SHA-256 is then recorded. Re-running a phase skips verified files and retries incomplete entries.

## Update procedure

Never edit a canonical source release. Push changes to GitHub, create a new release directory named by commit, install/update its isolated environment, run tests, and point only future phase runs to the new commit. Existing provenance remains tied to its original source commit.
