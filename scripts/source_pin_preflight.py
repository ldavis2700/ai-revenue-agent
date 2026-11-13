#!/usr/bin/env python3
"""Read-only release guard: refuse a staged source SHA older than tested candidate.

Supply authoritative read-back commit SHAs from the deployment provider and a
verified tested source SHA. This tool never accesses Railway or modifies Git.
Use a full local git clone containing all three commit objects.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")


class UnsafeRelease(RuntimeError):
    pass


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=False)


def require_commit(repo: Path, sha: str, label: str) -> None:
    if not SHA.fullmatch(sha or ""):
        raise UnsafeRelease(f"{label}: a full lowercase 40-character SHA is required")
    if git(repo, "cat-file", "-e", sha + "^{commit}").returncode:
        raise UnsafeRelease(f"{label}: commit absent from local clone; fetch history and retry")


def ancestor(repo: Path, old: str, new: str) -> bool:
    result = git(repo, "merge-base", "--is-ancestor", old, new)
    if result.returncode not in (0, 1):
        raise UnsafeRelease("Cannot compare commit ancestry using this clone")
    return result.returncode == 0


def evaluate(repo: Path, deployed: str, staged: str, candidate: str) -> dict:
    if not (repo / ".git").exists():
        raise UnsafeRelease("A complete local git checkout is required")
    for name, sha in (("deployed", deployed), ("staged", staged),
                      ("candidate", candidate)):
        require_commit(repo, sha, name)
    if not ancestor(repo, deployed, staged):
        raise UnsafeRelease("Staged source does not descend from deployed source")
    if not ancestor(repo, staged, candidate):
        raise UnsafeRelease("Staged source is not an ancestor of tested candidate; reconcile branches")
    count = git(repo, "rev-list", "--count", f"{staged}..{candidate}")
    if count.returncode or not count.stdout.strip().isdigit():
        raise UnsafeRelease("Could not count commits after staged source")
    behind = int(count.stdout.strip())
    result = {"safe_to_apply_exact_tested_source": behind == 0 and staged == candidate,
              "staged_behind_candidate_commits": behind,
              "deployed_sha": deployed,
              "staged_sha": staged,
              "candidate_sha": candidate}
    if not result["safe_to_apply_exact_tested_source"]:
        result["reason"] = "STAGED_SOURCE_STALE: do not apply; reconcile provider patch and retest exact revision"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--deployed-sha", required=True)
    parser.add_argument("--staged-sha", required=True)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.repo, args.deployed_sha, args.staged_sha,
                          args.candidate_sha)
    except UnsafeRelease as exc:
        print(json.dumps({"safe_to_apply_exact_tested_source": False,
                          "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["safe_to_apply_exact_tested_source"] else 2


if __name__ == "__main__":
    sys.exit(main())
