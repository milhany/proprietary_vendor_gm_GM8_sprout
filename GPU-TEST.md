# GM8 V415 GPU experiment

This branch stages a newer proprietary GPU set for GM8 / Adreno 505 on
LineageOS 19.1. It is an experimental hardware-test build, not a validated
replacement for the shipping vendor branch.

## What changes

- OpenGL driver: V331.0 (2018) -> V415.0, build a7d4a14 / Iba1deb6915,
  dated 2020-07-23.
- 39 existing ARM and ARM64 library paths, covering EGL/GLES, GSL, C2D,
  OpenCL, Vulkan and matching RenderScript/compiler/debug companions.
- All candidate bytes come from beingstargazer/vendor_xiaomi_santoni,
  revision d476641987d8cc6c861b48dd9bffac8f9167ce53.
- HWC/gralloc HALs, GPU firmware, kernel and partition layout are unchanged.
- The normal lineage-19.1 vendor branch is retained as the rollback source.

The initially examined V502 set was rejected because it introduced newer
QTI mapper/gralloc dependencies. Do not mix files from that set into V415.

## Validation and limits

CI downloads the pinned original and donor files, checks their exact Git
blob hashes and sizes, confirms ARM/ARM64 ELF classes and SONAMEs, reads
the real embedded GL version, and compares dependency names. Existing
baseline dependency names may be provided by source-built platform/VNDK
libraries rather than the extracted vendor directory.

See tools/gpu-import-verification.json for file SHA-256 values and results.
These checks do not prove symbol-version compatibility, linker namespace
visibility, 3.18 KGSL ioctl compatibility, or correct device behavior.
Those remain hardware/build-host tests. No performance or flicker fix is
claimed until the phone has been tested.

The matching device branch includes automatic speed compilation for normal
app installs/background maintenance and disables forced unsignaled buffer
latching. If both device and vendor changes are first installed together,
the effects of those changes have not been isolated from each other.

## Build on the existing server

Keep a copy of the currently working signed OTA/recovery before testing.
Do not discard local changes when switching repositories. The existing
legacy protobuf fixups are unrelated to these GPU library paths.

Run inside the builder container, using bash:

    cd ~/android/lineage-19.1
    set -o pipefail

    git -C device/gm/GM8_sprout fetch https://github.com/milhany/android_device_gm_GM8_sprout.git lineage-19.1 &&
    git -C device/gm/GM8_sprout switch --detach FETCH_HEAD &&
    git -C vendor/gm/GM8_sprout fetch https://github.com/milhany/proprietary_vendor_gm_GM8_sprout.git lineage-19.1-gpu-test &&
    git -C vendor/gm/GM8_sprout switch --detach FETCH_HEAD &&
    source build/envsetup.sh &&
    lunch lineage_GM8_sprout-user &&
    python3 device/gm/GM8_sprout/tools/preflight.py &&
    m target-files-package otatools -j32 2>&1 | tee ~/android/gm8-gpu415-build.log

Do not install the target-files ZIP itself. Sign it through the existing
release helper and generate the OTA. Reuse the same private keys from the
previous release. Choose a fresh output directory so earlier artifacts
remain available:

    python3 device/gm/GM8_sprout/tools/release-19.1.py prepare \
      --top . \
      --target-files out/target/product/GM8_sprout/obj/PACKAGING/target_files_intermediates/lineage_GM8_sprout-target_files-eng.builder.zip \
      --key-dir ../gm8-signing/keys \
      --output-dir ../gm8-signing/gpu415-test-20261020 &&
    python3 device/gm/GM8_sprout/tools/release-19.1.py sign \
      --top . \
      --output-dir ../gm8-signing/gpu415-test-20261020

The filename containing eng.builder does not determine the build variant;
the archive properties must say user and release-keys after signing.
Confirm the final Verified signed OTA message before installation.
If the phone is already using this release key set, do not generate a new
key set for this experiment. Initial migration from test keys still follows
the clean-install plan already documented in the device release guide.

## Test on the phone

For the HWC test, turn OFF the developer option named
"Disable HW overlays" (Turkish: "HW bindirmelerini devre disi birak").
Otherwise the GPU-composition workaround masks the original symptom.

    adb shell dumpsys SurfaceFlinger | findstr /I "GLES"
    adb shell getprop debug.sf.latch_unsignaled
    adb shell getprop pm.dexopt.install
    adb shell getprop pm.dexopt.bg-dexopt

Expected: Adreno 505 / V@415.0, then 0, speed, speed.

Check the specific images/scrolling that flickered, Snapchat camera/lenses
and recording, both stock cameras, video playback, screen recording,
screen rotation, suspend/wake and both 32-bit and 64-bit graphics clients.
Compare app launch timings separately; AOT compilation is another change.
Capture logs before enabling the overlay workaround again if possible.

## Roll back

The known original vendor revision is
69e3e328f2d2634643a562186f9c9c403397a0c5. Fetch and select the shipping
lineage-19.1 vendor branch, rebuild and sign with the same private keys.
Retain the newer device fixes if testing them independently:

    git -C vendor/gm/GM8_sprout fetch https://github.com/milhany/proprietary_vendor_gm_GM8_sprout.git lineage-19.1 &&
    git -C vendor/gm/GM8_sprout switch --detach FETCH_HEAD

No bootloader replacement, relocking, partition resizing or phone flashing
is performed by the audit/import scripts.
