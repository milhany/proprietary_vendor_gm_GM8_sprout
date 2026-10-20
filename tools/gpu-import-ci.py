#!/usr/bin/env python3
"""Stage an audited candidate on the isolated GPU experiment branch only."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import importlib.util

def git(*args, **kwargs):
    return subprocess.check_output(["git", *args], text=True, **kwargs).strip()

def main():
    if os.environ.get("GITHUB_REF") != "refs/heads/lineage-19.1-gpu-test":
        raise ValueError("GPU import is restricted to its experimental branch")
    root = Path.cwd()
    manifest = json.loads((root / "tools/gpu-candidate.json").read_text())
    work = Path(os.environ["RUNNER_TEMP"]) / "gm8-gpu-audit"
    report = json.loads((work / "gpu-report.json").read_text())
    if not report["static_checks_passed"] or report["errors"]:
        raise ValueError("Candidate did not pass the static audit")
    if report["donor_commit"] != manifest["donor_commit"]:
        raise ValueError("Audit and manifest do not match")
    current = {}
    modes = {}
    for row in manifest["files"]:
        path = row["path"]
        current[path] = git("rev-parse", "HEAD:" + path)
        modes[path] = git("ls-tree", "HEAD", "--", path).split()[0]
    if all(current[row["path"]] == row["donor_sha"] for row in manifest["files"]):
        print("All candidate libraries already imported; no commit required.")
        return
    if any(current[row["path"]] not in (row["original_sha"], row["donor_sha"])
           for row in manifest["files"]):
        raise ValueError("GPU files diverged from the reviewed baseline")
    changed = [row["path"] for row in manifest["files"]
               if current[row["path"]] != row["donor_sha"]]
    for row in manifest["files"]:
        target = root / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / "original" / row["path"], target)
        target.chmod(0o755 if modes[row["path"]] == "100755" else 0o644)
    subprocess.check_call([sys.executable, "tools/gpu-compare.py",
                           "--work", str(work), "--stage-root", str(root)])
    report.pop("removed_gpu_exports", None)
    report["undefined_symbols_verified"] = False
    report["device_tested"] = False
    report["source"] = {
        "repository": manifest["donor_repository"],
        "revision": manifest["donor_commit"],
        "baseline": manifest["original_commit"],
    }
    report_path = "tools/gpu-import-verification.json"
    (root / report_path).write_text(json.dumps(report, indent=2) + "\n")
    paths = [row["path"] for row in manifest["files"]] + [report_path]
    subprocess.check_call(["git", "add", "--sparse", "--", *paths])
    actual = set(git("diff", "--cached", "--name-only").splitlines())
    if actual != set(changed + [report_path]):
        raise ValueError("Staged file set differs from the approved GPU inventory")
    for row in manifest["files"]:
        if git("rev-parse", ":" + row["path"]) != row["donor_sha"]:
            raise ValueError("Staged blob differs from the pinned donor")
    subprocess.check_call(["git", "config", "user.name", "github-actions[bot]"])
    subprocess.check_call(["git", "config", "user.email",
                           "41898282+github-actions[bot]@users.noreply.github.com"])
    subprocess.check_call(["git", "commit", "-m",
        "gm8: stage audited V415 graphics libraries for hardware testing\n\n"
        "Replace 39 existing ARM/ARM64 GPU libraries from the pinned Santoni\n"
        "Android 10 set. CI verified Git blob hashes, ELF architecture, SONAMEs,\n"
        "dependency names and the V331 -> V415 embedded GL version change.\n\n"
        "Keep firmware, HWC/gralloc HALs and the kernel unchanged. Full symbol\n"
        "resolution, 3.18 KGSL compatibility, boot and flickering remain untested.\n"
        "This commit belongs only to lineage-19.1-gpu-test."])
    subprocess.check_call(["git", "push", "origin",
                           "HEAD:refs/heads/lineage-19.1-gpu-test"])
    print("Imported GPU candidate commit:", git("rev-parse", "HEAD"))

if __name__ == "__main__":
    main()
