# Report unvalidated Apple SMC temperatures as unavailable

Level: Judged
Decided by: agent
Rests on: GPU-003/004/006 require attributable native values, raw evidence and honest availability. Retained M1 Pro idle/load observations expose an inactive-value ambiguity independently documented by OSHI.
Would be wrong if: A documented native validity signal makes the guard unnecessary, a supported source emits inactive values above this bound, or the application presents this software plausibility policy as a hardware fact.

## Decision

Use an explicit software plausibility guard for the attributed Apple Silicon SMC temperature keys. Preserve every successful native read and its original bytes, type, units and query window. A finite SMC temperature below 15 degrees Celsius has no displayed value and is Unavailable with a reason that names the conservative SMC plausibility guard; it is not classified as an absent API or permission failure.

At or above 15, a successfully decoded attributable SMC reading may be published unchanged. Reevaluate each sample so a sensor recovers immediately; never clamp, subtract a guessed offset, or refresh a cached temperature. Keep key identity and per-source failure handling independent.

This guard does not apply to HID temperatures or other quantities. It can withhold a real cold SMC reading and cannot prove that every higher value is valid; record that limitation in source capabilities and native coverage. The bound is an explicit software policy, not a vendor-defined validity bit or operating-temperature specification.

Root retained native M1 Pro idle/load captures show the two attributed keys at about 9.2 while idle and about 47-50 under Metal load. Upstream OSHI independently documents inactive Apple sensor sentinels and uses this same conservative lower plausibility bound: [pinned OSHI source](https://github.com/oshi/oshi/blob/9ecde13ae454b2deac89bc7c15e4f38be92307ed/oshi-core/src/main/java/oshi/util/platform/mac/SmcUtil.java#L206-L230).

Falsifiers include idle 9.2 becoming current, failure being reported as a low value, missing raw operands, no recovery under load, applying this bound to a valid HID temperature, and advertising the policy as hardware truth. Test the exact boundary and retained availability reason. Native accuracy and other Apple hardware remain subject to their required evidence.

## Realized by

(none yet: recorded, not built)
