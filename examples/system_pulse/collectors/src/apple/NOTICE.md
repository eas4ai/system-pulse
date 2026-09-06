# Native source notices

The SMC request layout and frequency-pair interpretation were informed by and
adapted from macmon 0.8.2. The complete upstream notice follows.

MIT License

Copyright (c) 2024 vladkens

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Native bindings were checked against the retained read-only source probes and
Apple's published IOKit and IOReport type definitions. HardwareVisualizer was
used as a memory-source lead; its implementation was not copied.

The M1 GPU SMC key names come from the pinned Stats sensor table linked in
`docs/execution/intel-and-apple-gpus/apple-source-probe.md`. The SMC result 0x84
is the key-not-found result documented by the maintained SMCKit implementation:
https://github.com/beltex/SMCKit/blob/master/SMCKit/SMC.swift

The conservative SMC software plausibility policy is recorded separately in
`docs/decisions/report-unvalidated-apple-smc-temperatures-as-unavailable.md`.
No OSHI implementation is copied.

## Stats sensor-key table

Exact model/key mappings are adapted from Stats at commit
6ef61b71de53eab400f811456ddeac5bef631308. Its notice follows.

MIT License

Copyright (c) 2019 Serhiy Mytrovtsiy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
