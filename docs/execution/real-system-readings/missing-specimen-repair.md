# Missing-device specimen repair

The failed aggregate retained its native evidence at
`/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/`.
Comparing `missing-device-config.json` with `state/workspace.json` shows one dock
change: `/dock/center/info/stack/sizes/153` went from 280 to 36. CPU was marked
collapsed in both files. Memory's `expanded_size.width` also changed from 1342
to 2848 outside the dock tree.

The specimen writer combined launch dock geometry with preferences saved after
the preset and recovery cases. That gave the collapsed CPU an expanded dock
height. The evidence identifies an inconsistent specimen; it does not establish
an application persistence defect.

The replay now retains one complete actual workspace capture. Focused
missing-device runs use the launch capture. Full runs refresh it immediately
before the physical split, preserving the sensor choices exercised earlier.
The stopped-app specimen copies that capture, substitutes the selected real
device's dock identity with `:saved-absent`, and retains the real identity as
saved-hidden. Its metadata and sensor preferences come from the same capture.
No runtime measurements are supplied. Exact dock equality and all existing
missing-device, status, and native assertions remain unchanged.

The regression runs the production specimen writer until the native launch
boundary. With the old writer it failed because later collapsed preferences
leaked into the earlier dock. After the repair both focused tests pass. They
also check exact dock substitution, saved-hidden original identity, metadata,
sensor preferences, and capture immutability.

Verification performed:

- Focused RED: 2 tests ran; the cross-phase regression failed as expected.
- Focused GREEN: 2 tests passed.
- `rtk proxy python3 -B -m unittest discover -s scripts/system-pulse -p 'test_*.py' -v`:
  51 tests passed.
- `rtk git diff --check`: passed.

No Python formatter or linter is configured in the acceptance runner. Native
and aggregate reruns remain pending independent review. Physical device removal
remains unverified; this is a stopped-app configuration specimen.

## Independent review

SPEC PASS at `24533a15`: all 51 Python tests passed independently; the new regression reproduced the baseline defect and the identity control passed. QUALITY PASS at the same source: two focused tests and commit-range whitespace check passed; complete capture timing, immutable copy, preservation and unchanged native assertions inspected. Native and aggregate evidence remain pending.
