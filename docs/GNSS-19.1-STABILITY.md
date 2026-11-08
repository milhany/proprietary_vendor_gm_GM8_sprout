# GM8 GNSS init mapping for LineageOS 19.1

Associate the existing `gnss_service` init stanza with
`android.hardware.gnss@2.0::IGnss/default`. The service binary, credentials,
groups, class and startup policy remain unchanged. This is the same
one-line mapping prepared for the Android 10 stability candidate.

The change resolves init interface lookup; it does not establish GNSS fix
success, XTRA injection or improved satellite reception. Android init/build
and physical phone acceptance remain pending.

Base: `69e3e328f2d2634643a562186f9c9c403397a0c5`.
Use with the paired device/kernel `lineage-19.1-stability-20261108` branch.
