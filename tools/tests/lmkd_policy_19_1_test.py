#!/usr/bin/env python3
"""Exercise actual GM8 post-boot code without accessing host sysfs or swap."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
from ppr_policy_19_1_test import main as test_legacy_paths


def userspace(source, ppr, fallback):
    function = source.split('function configure_memory_parameters() {', 1)[1].split(
        'function enable_memory_features()', 1)[0]
    function = 'function configure_memory_parameters() {' + function
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        soc = ('sys/devices/system/soc/soc0/id' if fallback else 'sys/devices/soc0/soc_id')
        files = {soc: '313', 'proc/sys/vm/swappiness': '60',
                 'sys/module/vmpressure/parameters/allocstall_threshold': '1'}
        if ppr is not None:
            files['sys/module/process_reclaim/parameters/enable_process_reclaim'] = str(ppr)
        for name, value in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        function = re.sub(r'/(?:sys|proc)/', lambda m: str(root) + m[0], function)
        script = '''
configure_zram_parameters() { echo zram; }
configure_read_ahead_kb_values() { echo readahead; }
enable_swap() { echo swap; }
getprop() { echo UNEXPECTED_LEGACY_PATH >&2; return 1; }
''' + function + '\nconfigure_memory_parameters\n'
        result = subprocess.run(['bash', '-e', '-c', script], capture_output=True, text=True)
        assert result.returncode == 0 and not result.stderr, result.stderr
        assert result.stdout.splitlines() == ['zram', 'readahead', 'swap']
        assert (root / 'proc/sys/vm/swappiness').read_text().strip() == '100'
        assert (root / 'sys/module/vmpressure/parameters/allocstall_threshold').read_text().strip() == '0'
        if ppr is not None:
            assert (root / 'sys/module/process_reclaim/parameters/enable_process_reclaim').read_text().strip() == '0'
        assert not (root / 'sys/module/lowmemorykiller').exists()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor', type=Path, required=True)
    args = parser.parse_args()
    source = (args.vendor / 'proprietary/vendor/bin/init.qcom.post_boot.sh').read_text()
    for ppr in (None, 0, 1):
        for fallback in (False, True):
            userspace(source, ppr, fallback)
    print('PASS: actual GM8 userspace-LMK path, six missing/present-PPR and SoC-path cases')
    # Existing tests cover old-kernel GM8, other SoCs, real zRAM size function
    # and mkswap/swapon order; those paths must retain their behavior.
    test_legacy_paths()
