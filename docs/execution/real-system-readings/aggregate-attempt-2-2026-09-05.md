# Reviewed aggregate: final missing-device failure

Tested commit: `93747be63e317ef0392cc8abc27a385ff5e88a4b`.
Implementation: `8ffa088bffeeac1a4743170cff93bf2eec0847b8`.
Result: **FAIL**. Task 3 and final acceptance remain incomplete.

The run passed all 400 tests (49 Python, 351 Rust), source guard, scoped formatting, strict Clippy, locked builds, and diff checking. Fresh host acceptance passed 41,674 counter brackets with zero missing, 468 independent stable-total checks, 2,237 sensor comparisons, 16,201 process field checks, and 100 interface comparisons. NVIDIA hardware accuracy remains unverified.

Thirteen native cases passed. The final missing-device case failed `missing specimen dock changed`. A recursive comparison of the retained input specimen and subsequently saved workspace found exactly one dock difference: `dock/center/info/stack/sizes/153`, from 280 to 36. The corresponding panel is `cpu:host`, whose specimen preference already says `collapsed: true`. There were no added or removed dock identities.

The retained harness replaces the dock with `initial_dock` while retaining later panel preferences. This evidence points to an internally inconsistent specimen; it does not establish a product defect. The recommended next step is to make the specimen's dock and collapse preferences consistent, preserve exact layout and missing-device assertions, add a regression for this composition, and independently review before another aggregate. Do not waive the discrepancy or fabricate measurements.

Six preceding app sessions exited normally with code 0. Failure cleanup terminated the last app with -15; every recorded app PID was absent afterward. Shared transport exited 0, with no surviving PID, forced kill, or cleanup errors. The missing-device case did not reach its complete native assertions or normal shutdown validation.

Cairn recorded the third consecutive failed aggregate receipts and named `escalate LIVE-001` under DEC-016. No fourth aggregate or implementation change has been started.

Artifacts and SHA-256 digests:

```json
{
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/failure.json": "801608b2936e670a55954bbb0866a7f89dd73f85d1ce15fa061532cba71c8844",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/host/result.json": "cfb5342439a5cb28858e674784b7876a069209d5380527f0ad19577c084c28ab",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/result.json": "e5bf041ca8bfcb6e8d7129392ae63b5d13de5da761ed9080cde4e3a2c3d5a616",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/missing-device-config.json": "42038a18ac38347edbbab916740a85c190b71673d3bb5d29b0a44f7c8f7892d7",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/state/workspace.json": "9cc47a0679adf28753e6bc15f4d0d90e01dc8dbd25ae3fbf3787e2b832aa0b14",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/session-missing-device/failure-frame.json": "137325556eb482ba58a67fa9bf56d20c8ba7d6e5f917dfe704dc80d7be9c7024",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/session-missing-device/failure.png": "4e163af9d70584d752f8f4c7fc89c713bb7bdc3ae682cf1490c402d0e2a1ec01",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/session-missing-device/journal.jsonl": "49d3d125ce7f3c23312ece245e0aa2ce0366edddf90b540a271c56e78240c73e",
  "/tmp/system-pulse-cairn-check-8czjw7vp/system-pulse-acceptance-2zl2nswb/native/transport-cleanup.json": "def315398070474483f8811687709f4313ba0344202ac6dcfbf84c9fa5bd2751"
}
```
