# University H100 server runbook

## Verified endpoint and capacity

- SSH: `wangpeng@127.0.0.1`, port `1022`
- Required identity: hostname `kemove-Rack-Server`, user `wangpeng`
- Raw/canonical proposal: `/private_nas/wangpeng/cognition-and-consciousness`
- Fast active work proposal: `/data1/wangpeng/cognition-and-consciousness-work`
- Restartable work proposal: `/data2/wangpeng/cognition-and-consciousness-work`
- Scheduler: no Slurm; use `tmux`

The root paths above remain proposals until the owner confirms them. Do not create alternate roots by guesswork.

## Authorized deployment scope

The current owner instruction authorizes **data acquisition only for execution**. Deploy the
sparse acquisition release and queue P01/P02 only. On 2026-09-10 the owner additionally
authorized **inactive source staging only**. Do not activate the staged analysis source,
create a scientific Python environment, or queue P03-P10 without separate explicit permission.

The verified inactive snapshot and unchanged active-source checks are recorded in
[`SERVER_STAGING_c1a6e64.md`](SERVER_STAGING_c1a6e64.md). That operation used the existing
fast-work source parent; it did not confirm all proposed storage roots or create `/data2`
work directories. The configuration's `deployment_scope=acquisition_only` remains unchanged.

## First acquisition deployment

1. Verify `hostname` and `id -un` in the same SSH session used for writes.
2. Obtain explicit owner confirmation for all three roots and commit
   `roots_status=owner_confirmed`; do not infer paths.
3. Copy only `scripts/server/deploy_acquisition_release.sh` to a temporary server location and run:

```bash
deploy_acquisition_release.sh <commit> \
  /private_nas/wangpeng/cognition-and-consciousness \
  /data1/wangpeng/cognition-and-consciousness-work \
  /data2/wangpeng/cognition-and-consciousness-work \
  --confirm-roots
```

4. Enter the returned immutable sparse-release directory. It contains only acquisition code,
   configuration, and the acquisition runner—not the analysis pipeline.
5. Queue P01 and wait for its terminal marker before P02:

```bash
scripts/server/queue_acquisition.sh resolve
scripts/server/queue_acquisition.sh download
```

The default P02 order obtains small anchors first, then the larger OpenNeuro/BMVP releases. It
continues after a source-specific failure and returns a failed aggregate marker if any eligible
source failed. Re-running the same command resumes partial downloads and skips verified files.

No password belongs in these commands. The local SSH password is entered only at an interactive prompt.

## Layout

```text
canonical_root/
  source/acquisition-releases/<git-commit>/
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

Source releases are content-addressed and not edited in place. Raw archives are retained and
extraction targets are separate. A conflicting pre-existing file is renamed with an
`.invalid-<timestamp>` suffix before replacement; the `quarantine` directory is reserved for later
structural review. Nothing is automatically deleted.

## Monitoring and recovery

```bash
tmux ls
tmux attach -t factorcon-P02
scripts/server/status.sh
tail -n 100 /private_nas/wangpeng/cognition-and-consciousness/logs/P02/latest.log
```

Downloaders use `.part` files and resume with HTTP Range when supported. A file becomes complete only after expected-size and available upstream hash checks pass; a local SHA-256 is then recorded. Re-running a phase skips verified files and retries incomplete entries.

Before each P02 family, `CAPACITY.<family>.json` compares its unresolved manifest estimate with
live NAS free space.
During transfer, the downloader protects a 500 GiB reserve even for upstream objects without a
declared size. Reaching that reserve stops new submissions and preserves `.part` files for a later
resume.

## Update procedure

Never edit a canonical acquisition release. Push changes to GitHub and create a new sparse release
directory named by commit. Acquisition uses the server's Python 3.12 standard library and requires
no scientific environment. Existing data provenance remains tied to its original source commit.
