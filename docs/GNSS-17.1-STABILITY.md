# GNSS init interface registration

The existing GNSS service uses android.hardware.gnss@2.0-service-qti but its
init stanza did not associate `android.hardware.gnss@2.0::IGnss/default`.
Framework interface-start requests therefore could not resolve that
service through init's interface mapping.

Add the interface line to the existing service without changing its
binary, user, groups, class or startup policy. This is an init lookup fix;
it does not establish successful GNSS fixes, XTRA injection or RF reception.

Prepared 2026-11-08 against vendor revision
`a22c80f76f1bc90d07d627bd43af8e959e3b22bc`. Patch application/reverse checks
passed. Full Android init/build and hardware acceptance are pending.
Use with the matching device/kernel `lineage-17.1-stability-20261108` branch.
