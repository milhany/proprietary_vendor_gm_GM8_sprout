#!/usr/bin/env python3
"""Run the actual vendor memory function against substitute sysfs/proc files."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def execute(source, soc, initial):
    start = source.index("function configure_memory_parameters() {")
    end = source.index("function enable_memory_features()", start)
    function = source[start:end]
    with tempfile.TemporaryDirectory(prefix="gm8-ppr-policy-") as directory:
        root = Path(directory)
        initial_files = {
            "proc/meminfo": "MemTotal:        2891416 kB\n",
            "sys/devices/soc0/soc_id": str(soc),
            "sys/module/lowmemorykiller/parameters/adj": "0,100,200,250,900,950",
            "sys/module/lowmemorykiller/parameters/minfree": "18432,23040,27648,32256,64512,80640",
            "sys/module/process_reclaim/parameters/enable_process_reclaim": str(initial),
        }
        for path, value in initial_files.items():
            output = root / path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(value)
        for path in ("proc/sys/vm", "sys/module/vmpressure/parameters"):
            (root / path).mkdir(parents=True)
        function = re.sub(r"/(?:sys|proc)/", lambda match: str(root) + match[0], function)
        # Every sysfs/proc operation in the actual function is redirected above.
        script = """
getprop() { case "$1" in ro.product.name) echo GM8;; ro.config.low_ram) echo false;; esac; }
uname() { echo aarch64; }
configure_zram_parameters() { echo zram; }
configure_read_ahead_kb_values() { echo readahead; }
enable_swap() { echo swap; }
disable_core_ctl() { echo corectl; }
""" + function + "\nconfigure_memory_parameters\n"
        result = subprocess.run(["bash", "-e", "-c", script], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        read = lambda path: (root / path).read_text().strip()
        assert read("sys/module/lowmemorykiller/parameters/adj") == initial_files["sys/module/lowmemorykiller/parameters/adj"]
        assert read("sys/module/lowmemorykiller/parameters/minfree") == initial_files["sys/module/lowmemorykiller/parameters/minfree"]
        assert read("sys/module/lowmemorykiller/parameters/enable_adaptive_lmk") == "1"
        assert read("sys/module/lowmemorykiller/parameters/adj_max_shift") == "606"
        assert read("proc/sys/vm/swappiness") == "100"
        assert result.stdout.splitlines() == ["zram", "readahead", "swap"]
        return read("sys/module/process_reclaim/parameters/enable_process_reclaim"), root.joinpath(
            "sys/module/process_reclaim/parameters/min_score_adj").exists()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", type=Path, required=True)
    args = parser.parse_args()
    relative = "proprietary/vendor/bin/init.qcom.post_boot.sh"
    current = (args.vendor / relative).read_text()
    baseline = subprocess.check_output(["git", "show", "440a2383046cdbe824f7695a3e8ced49a35ea7db:" + relative],
                                       cwd=args.vendor, text=True)
    assert execute(baseline, 313, 0)[0] == "1"
    assert execute(current, 313, 0) == ("0", False)
    assert execute(current, 313, 1) == ("0", False)
    assert execute(current, 294, 0) == execute(baseline, 294, 0) == ("1", True)
    assert execute(current, 321, 0) == execute(baseline, 321, 0) == ("0", False)
    print("PASS: actual GM8 memory function stops PPR even if previously enabled")
    print("PASS: LMK thresholds, adaptive LMK and normal swap/zRAM calls preserved")
    print("PASS: other SoC branches retain their original behavior; modified function executes")


if __name__ == "__main__":
    main()
