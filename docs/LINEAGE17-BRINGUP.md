# GM8 Android 10 baseline

Initial lineage-17.1 vendor branch starts from
9eec7f5fbaffc9f24cb5af224ce5443da3760b5e, the stock-derived 18.1 rework
vendor snapshot. No V415 GPU import, Android 12 system_ext relocation,
1.5 GiB zRAM or userspace-LMK experiment is imported.

The binary baseline is not proof of Android 10 runtime compatibility. Check
GNSS, RIL/IMS, fingerprint, camera and audio services on hardware. The device
tree selects Android 10 audio HIDL 5.0 and its audio@2.0 service host; the
stock native DMS service and DAP processor remain supplied by this repository.

The existing libdlbmemoryservice ABuffer fixups target the layout used by
Android 11. Android 10 and 11 ABuffer headers were compared and match, but
this header comparison is not a complete native ABI or live DMS test.
The matching device source includes the fixup specification and the newer
controller with crash-loop protection and receiver/call-route bypass.

The original 18.1 manifest and binary hashes are retained for reproducibility.
Full source checks/build and runtime validation remain required. Do not
install vendor alone over the Android 12 ROM.
