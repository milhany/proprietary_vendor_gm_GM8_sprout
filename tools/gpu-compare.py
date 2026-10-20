#!/usr/bin/env python3
"""Audit a pinned GM8 GPU candidate; stage only after all static checks pass.

No phone access, flashing, firmware replacement or release-branch mutation.
Static checks cannot prove compatibility with the running 3.18 KGSL driver.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import struct
import subprocess
import sys
import urllib.request
from pathlib import Path

SYSTEM_LIBS = {
    "libc.so", "libm.so", "libdl.so", "liblog.so", "libc++.so",
    "libcutils.so", "libutils.so", "libbase.so", "libz.so", "libsync.so",
    "libhardware.so", "libnativewindow.so", "libvndksupport.so", "libion.so",
    "libEGL.so", "libGLESv1_CM.so", "libGLESv2.so", "libGLESv3.so",
    "libbinder.so", "libhidlbase.so", "libhidltransport.so", "libhwbinder.so",
}

def git_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def fetch(repo, commit, path, expected_sha, expected_size, destination):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Unpinned source revision")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        data = destination.read_bytes()
    else:
        url = "https://raw.githubusercontent.com/" + repo + "/" + commit + "/" + path
        request = urllib.request.Request(url, headers={"User-Agent": "GM8-GPU-audit/1"})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(expected_size + 1)
        if len(data) != expected_size or git_sha(data) != expected_sha:
            raise ValueError("Size or Git blob hash mismatch: " + path)
        destination.write_bytes(data)
    if len(data) != expected_size or git_sha(data) != expected_sha:
        raise ValueError("Cached blob hash mismatch: " + path)
    return destination

def inspect(path, arch):
    data = path.read_bytes()
    elf_class = 2 if arch == "lib64" else 1
    machine = 183 if arch == "lib64" else 40
    if (data[:4] != b"\x7fELF" or data[4:6] != bytes([elf_class, 1])
            or struct.unpack_from("<H", data, 16)[0] != 3
            or struct.unpack_from("<H", data, 18)[0] != machine):
        raise ValueError("Wrong ELF architecture/type: " + str(path))
    dynamic = subprocess.check_output(["readelf", "-dW", str(path)], text=True)
    symbols = subprocess.check_output(["readelf", "--dyn-syms", "--wide", str(path)], text=True)
    needed = re.findall(r"\(NEEDED\).*Shared library: \[([^\]]+)\]", dynamic)
    soname = re.findall(r"\(SONAME\).*Library soname: \[([^\]]+)\]", dynamic)
    exports, undefined = set(), set()
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[4] not in ("GLOBAL", "WEAK"):
            continue
        name = fields[7].split("@", 1)[0]
        if fields[6] == "UND":
            if fields[4] == "GLOBAL":
                undefined.add(name)
        else:
            exports.add(name)
    strings = re.findall(rb"[ -~]{6,}", data)
    version_text = [x.decode("ascii") for x in strings
                    if re.search(rb"V@[0-9]|GIT@|OpenGL ES.*V@|Date:", x)]
    majors = sorted(set(int(x) for x in re.findall(rb"V@([0-9]{3,4})", data)))
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "needed": needed, "soname": soname,
        "version_text": version_text[:20], "version_majors": majors,
        "exports": exports, "undefined": undefined,
    }

def serializable(info):
    return {key: sorted(value) if isinstance(value, set) else value
            for key, value in info.items() if key not in ("exports", "undefined")}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).with_name("gpu-candidate.json"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path,
                        help="Optional source vendor tree; requires pristine original blobs.")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest["format"] != 1 or len(manifest["files"]) != 39:
        raise ValueError("Unexpected candidate manifest")
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    jobs = []
    for row in manifest["files"]:
        path = row["path"]
        if not re.fullmatch(r"proprietary/vendor/lib(?:64)?/(?:egl/|hw/)?[A-Za-z0-9_.-]+\.so", path):
            raise ValueError("Path outside approved GPU library directories: " + path)
        jobs.append((manifest["original_repository"], manifest["original_commit"],
                     path, row["original_sha"], row["original_size"], work / "original" / path))
        jobs.append((manifest["donor_repository"], manifest["donor_commit"],
                     row["donor_path"], row["donor_sha"], row["donor_size"], work / "candidate" / path))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, *job) for job in jobs]
        for future in futures:
            future.result()
    report = {
        "donor_commit": manifest["donor_commit"],
        "original_commit": manifest["original_commit"],
        "static_checks_passed": False, "kernel_compatibility": "UNTESTED",
        "device_tested": False, "files": [], "errors": [],
        "notes": [
            "No GPU firmware, HWC/gralloc HAL, display-color or kernel files are replaced.",
            "Check build-host linker namespaces and vendor consumers before deployment.",
            "Boot, flickering, camera, video, suspend and both app ABIs need phone testing.",
        ],
    }
    replaced = {"lib": set(), "lib64": set()}
    versions = {"original": set(), "candidate": set()}
    for row in manifest["files"]:
        arch = row["path"].split("/")[2]
        replaced[arch].add(Path(row["path"]).name)
    old_exports = {"lib": set(), "lib64": set()}
    new_exports = {"lib": set(), "lib64": set()}
    for row in manifest["files"]:
        path = row["path"]
        arch = path.split("/")[2]
        old = inspect(work / "original" / path, arch)
        new = inspect(work / "candidate" / path, arch)
        old_exports[arch].update(old["exports"])
        new_exports[arch].update(new["exports"])
        if Path(path).name == "libGLESv2_adreno.so":
            versions["original"].update(old["version_majors"])
            versions["candidate"].update(new["version_majors"])
        if old["soname"] != new["soname"]:
            report["errors"].append("SONAME changed: " + path)
        available = (set(manifest["vendor_sonames"][arch]) | SYSTEM_LIBS
                     | replaced[arch] | set(old["needed"]))
        missing = sorted(set(new["needed"]) - available)
        if missing:
            report["errors"].append("Unresolved dependency names for " + path + ": " + repr(missing))
        report["files"].append({
            "path": path, "original": serializable(old), "candidate": serializable(new),
            "new_needed": sorted(set(new["needed"]) - set(old["needed"])),
            "removed_export_count": len(old["exports"] - new["exports"]),
            "added_strong_undefined_count": len(new["undefined"] - old["undefined"]),
        })
    report["versions"] = {key: sorted(value) for key, value in versions.items()}
    if not versions["candidate"] or not versions["original"]:
        report["errors"].append("Unable to identify actual GL driver versions")
    elif min(versions["candidate"]) <= max(versions["original"]):
        report["errors"].append("Candidate GL driver is not newer than the original")
    report["removed_gpu_exports"] = {
        arch: sorted(old_exports[arch] - new_exports[arch]) for arch in old_exports
    }
    report["static_checks_passed"] = not report["errors"]
    target_report = work / "gpu-report.json"
    target_report.write_text(json.dumps(report, indent=2) + "\n")
    print("GPU driver versions:", json.dumps(report["versions"]))
    for row in report["files"]:
        if row["new_needed"]:
            print("New dependencies:", row["path"], row["new_needed"])
    for message in report["errors"]:
        print("ERROR:", message)
    print("Audit:", target_report)
    print("Static checks:", "PASS" if report["static_checks_passed"] else "FAIL")
    print("3.18 KGSL / hardware compatibility: UNTESTED")
    if not report["static_checks_passed"]:
        return 1
    if args.stage_root:
        root = args.stage_root.resolve()
        for row in manifest["files"]:
            target = root / row["path"]
            if target.is_symlink() or not target.is_file():
                raise ValueError("Missing or symlink destination: " + str(target))
            if not target.resolve().is_relative_to(root):
                raise ValueError("Destination escapes source tree")
            if git_sha(target.read_bytes()) != row["original_sha"]:
                raise ValueError("Destination contains local changes: " + str(target))
        staged = []
        try:
            for row in manifest["files"]:
                target = root / row["path"]
                temporary = target.with_name(target.name + ".gm8-gpu-stage")
                if temporary.exists() or temporary.is_symlink():
                    raise FileExistsError(str(temporary))
                with temporary.open("xb") as stream:
                    stream.write((work / "candidate" / row["path"]).read_bytes())
                temporary.chmod(target.stat().st_mode & 0o777)
                temporary.replace(target)
                staged.append(row)
        except BaseException:
            for row in reversed(staged):
                (root / row["path"]).write_bytes((work / "original" / row["path"]).read_bytes())
            raise
        print("Staged", len(staged), "GPU libraries in", root)
        print("Original bytes remain in", work / "original")
    return 0

if __name__ == "__main__":
    sys.exit(main())
