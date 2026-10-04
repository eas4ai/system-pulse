use std::ffi::OsString;
pub(super) const MAGIC: u64 = 0x0001_5450_5543_5053;
const AMD_MAGIC: u64 = 0x0002_5450_5543_5053;
pub(super) type Result<T> = std::result::Result<T, String>;

/// Discriminates raw operands from the two fixed, approved temperature reads.
/// The wire tag prevents AMD SMN data being interpreted as Intel DTS registers.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Backend {
    Intel,
    AmdZen3,
}

impl Backend {
    pub fn for_cpu(vendor: &[u8; 12], signature: u32, thermal: u32) -> Option<Self> {
        let base_family = (signature >> 8) & 15;
        let family = base_family
            + if base_family == 15 {
                (signature >> 20) & 255
            } else {
                0
            };
        let model = ((signature >> 4) & 15)
            | if matches!(base_family, 6 | 15) {
                (signature >> 12) & 0xf0
            } else {
                0
            };
        match (vendor, family, model) {
            (b"GenuineIntel", 6, 0x9a) if thermal & (1 << 6) != 0 => Some(Self::Intel),
            (b"AuthenticAMD", 0x19, 0x21) => Some(Self::AmdZen3),
            _ => None,
        }
    }

    pub fn source(self) -> &'static str {
        match self {
            Self::Intel => "PawnIO / Intel package digital thermal sensor",
            Self::AmdZen3 => "PawnIO / AMD Zen 3 package Tctl/Tdie",
        }
    }

    #[cfg(target_os = "windows")]
    fn magic(self) -> u64 {
        match self {
            Self::Intel => MAGIC,
            Self::AmdZen3 => AMD_MAGIC,
        }
    }
}
#[derive(Debug, PartialEq, Eq)]
pub(super) struct Request {
    pub pid: u32,
    pub created: u64,
    pub nonce: String,
}
impl Request {
    pub fn parse(args: &[OsString]) -> Result<Self> {
        if args.len() != 3 {
            return Err("Expected caller PID, creation time and session nonce".into());
        }
        let text = args
            .iter()
            .map(|a| a.to_str().ok_or("Non-Unicode helper argument".to_string()))
            .collect::<Result<Vec<_>>>()?;
        for v in &text[..2] {
            if v.is_empty() || !v.bytes().all(|b| b.is_ascii_digit()) {
                return Err("Invalid caller identity".into());
            }
        }
        let pid: u32 = text[0].parse().map_err(|_| "Caller PID overflow")?;
        let created: u64 = text[1]
            .parse()
            .map_err(|_| "Caller creation time overflow")?;
        if pid == 0
            || created == 0
            || text[2].len() != 32
            || !text[2].bytes().all(|b| b.is_ascii_hexdigit())
        {
            return Err("Invalid caller identity or nonce".into());
        }
        Ok(Self {
            pid,
            created,
            nonce: text[2].to_ascii_lowercase(),
        })
    }
}
#[derive(Clone, Copy, Debug)]
pub(super) struct Frame {
    pub backend: Backend,
    pub sequence: u64,
    pub target: u64,
    pub status: u64,
    pub before: u64,
    pub after: u64,
    pub frequency: u64,
    pub error: u64,
}
impl Frame {
    pub fn validate_backend(&self, expected: Backend) -> Result<()> {
        if self.backend != expected {
            return Err("CPU temperature frame does not match the approved CPU backend".into());
        }
        Ok(())
    }
    pub fn validate_clock(&self, now: u64, frequency: u64, previous_after: u64) -> Result<()> {
        if self.frequency != frequency
            || self.before < previous_after
            || self.after > now
            || now - self.after > frequency.saturating_mul(3)
        {
            return Err("CPU temperature query clock is mismatched, stale or out of order".into());
        }
        Ok(())
    }
    pub fn decode(bytes: &[u8], previous: u64) -> Result<Self> {
        if bytes.len() != 64 {
            return Err("Invalid CPU temperature frame length".into());
        }
        let (chunks, _) = bytes.as_chunks::<8>();
        let w: [u64; 8] = std::array::from_fn(|index| u64::from_le_bytes(chunks[index]));
        let backend = match w[0] {
            MAGIC => Backend::Intel,
            AMD_MAGIC => Backend::AmdZen3,
            _ => return Err("Invalid CPU temperature frame source".into()),
        };
        if w[1] == 0
            || w[1] <= previous
            || w[6] == 0
            || w[4] > w[5]
            || w[5] - w[4] > w[6]
            || w[7] > 8
        {
            return Err("Invalid CPU temperature frame metadata".into());
        }
        let frame = Self {
            backend,
            sequence: w[1],
            target: w[2],
            status: w[3],
            before: w[4],
            after: w[5],
            frequency: w[6],
            error: w[7],
        };
        if frame.error == 0 {
            frame.temperature()?;
        } else if frame.target != 0 || frame.status != 0 {
            return Err("Error frame contains temperature operands".into());
        }
        Ok(frame)
    }
    pub fn temperature(&self) -> Result<f64> {
        if self.error != 0 {
            return Err(error_reason(self.error).into());
        }
        if self.backend == Backend::AmdZen3 {
            return amd_temperature(self.target, self.status);
        }
        let target = ((self.target >> 16) & 255) as i32;
        let value = target - ((self.status >> 16) & 127) as i32;
        if self.status & (1 << 31) == 0
            || !(50..=125).contains(&target)
            || !(-40..=125).contains(&value)
        {
            return Err(
                "CPU package digital temperature is invalid or outside supported range".into(),
            );
        }
        Ok(f64::from(value))
    }
    #[cfg(target_os = "windows")]
    pub fn encode(self) -> [u8; 64] {
        let mut out = [0; 64];
        let (chunks, _) = out.as_chunks_mut::<8>();
        for (bytes, value) in chunks.iter_mut().zip([
            self.backend.magic(),
            self.sequence,
            self.target,
            self.status,
            self.before,
            self.after,
            self.frequency,
            self.error,
        ]) {
            bytes.copy_from_slice(&value.to_le_bytes());
        }
        out
    }
}
pub(super) fn error_reason(code: u64) -> &'static str {
    match code {
        1 => {
            "CPU temperature supports Intel Alder Lake model 0x9a with package DTS or AMD Zen 3 family 0x19 model 0x21"
        }
        2 => "CPU package temperature requires exactly one physical CPU package",
        3 => {
            "PawnIO driver is missing or could not be opened; install the approved driver separately"
        }
        4 => "PawnIO rejected the bundled signed CPU temperature module",
        5 => "PawnIO CPU temperature register read failed",
        6 => "CPU package temperature reading or processor affinity is invalid",
        7 => "CPU temperature helper clock failed",
        8 => "CPU temperature timed out waiting for the shared PCI access mutex; enable to retry",
        _ => "Unknown CPU temperature helper failure",
    }
}

/// Converts the fixed Zen 3 THM_TCON_CUR_TMP register to package Tctl/Tdie.
/// RANGE_SEL or TJ_SEL=3 selects the documented 49 Celsius range correction;
/// other generations and caller-selected registers never reach this decoder.
fn amd_temperature(raw: u64, reserved: u64) -> Result<f64> {
    if raw > u64::from(u32::MAX) || reserved != 0 {
        return Err("Invalid AMD temperature register operands".into());
    }
    let correction = raw & (1 << 19) != 0 || raw & (3 << 16) == 3 << 16;
    let value = ((raw >> 21) as f64 * 0.125) - if correction { 49. } else { 0. };
    if !(-40.0..=125.0).contains(&value) {
        return Err("AMD package temperature is outside supported range".into());
    }
    Ok(value)
}
pub(super) fn package_affinity(bytes: &[u8]) -> Result<(u16, u64)> {
    // SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX / PROCESSOR_RELATIONSHIP, x64 ABI.
    if bytes.len() < 48 || bytes.len() > 65536 {
        return Err("Invalid package topology length".into());
    }
    let relation = u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]);
    let size = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]) as usize;
    let count = usize::from(u16::from_le_bytes([bytes[30], bytes[31]]));
    // Exactly one record: a second package or trailing data is unsupported.
    if relation != 3 || size != bytes.len() || count == 0 || size != 32 + count * 16 {
        return Err("CPU temperature requires one unambiguous physical package".into());
    }
    let mask = u64::from_le_bytes([
        bytes[32], bytes[33], bytes[34], bytes[35], bytes[36], bytes[37], bytes[38], bytes[39],
    ]);
    let group = u16::from_le_bytes([bytes[40], bytes[41]]);
    if mask == 0 {
        return Err("Package has no active processor".into());
    }
    Ok((group, 1u64 << mask.trailing_zeros()))
}
#[cfg(test)]
mod tests {
    use super::*;
    fn args() -> Vec<OsString> {
        [
            "42",
            "134123456789000001",
            "0123456789abcdef0123456789abcdef",
        ]
        .map(OsString::from)
        .to_vec()
    }
    fn bytes(words: [u64; 8]) -> Vec<u8> {
        words.into_iter().flat_map(u64::to_le_bytes).collect()
    }
    fn good() -> [u64; 8] {
        [
            MAGIC,
            1,
            100 << 16,
            (1 << 31) | (65 << 16),
            100,
            110,
            10_000_000,
            0,
        ]
    }
    #[test]
    fn exact_request_preserves_creation_ticks() -> Result<()> {
        assert_eq!(
            Request::parse(&args())?,
            Request {
                pid: 42,
                created: 134123456789000001,
                nonce: "0123456789abcdef0123456789abcdef".into()
            }
        );
        Ok(())
    }
    #[test]
    fn malformed_requests_never_add_operations_or_paths() {
        for (index, values) in [
            (0, vec!["0", "4294967296", "+42", " 42", "４２"]),
            (1, vec!["0", "18446744073709551616", "-1", "1.0"]),
            (
                2,
                vec![
                    "abc",
                    "0123456789abcdef0123456789abcdeg",
                    "../../module.bin",
                    "0123456789abcdef0123456789abcdeé",
                ],
            ),
        ] {
            for value in values {
                let mut a = args();
                a[index] = value.into();
                assert!(Request::parse(&a).is_err(), "{value}");
            }
        }
        let mut a = args();
        a.push("0x1a0".into());
        assert!(Request::parse(&a).is_err());
        assert!(Request::parse(&args()[..2]).is_err());
    }
    #[test]
    fn valid_package_frame_retains_raw_operands() -> Result<()> {
        let f = Frame::decode(&bytes(good()), 0)?;
        assert_eq!(f.temperature()?, 35.0);
        assert_eq!(f.status, (1 << 31) | (65 << 16));
        Ok(())
    }
    #[test]
    fn remote_clock_must_match_local_frequency_and_be_fresh_and_ordered() -> Result<()> {
        let f = Frame::decode(&bytes(good()), 0)?;
        assert!(f.validate_clock(120, 10_000_000, 99).is_ok());
        assert!(f.validate_clock(109, 10_000_000, 99).is_err());
        assert!(f.validate_clock(40_000_000, 10_000_000, 99).is_err());
        assert!(f.validate_clock(120, 1, 99).is_err());
        assert!(f.validate_clock(120, 10_000_000, 101).is_err());
        Ok(())
    }
    #[test]
    fn rejects_malformed_replayed_and_impossible_frames() {
        let b = bytes(good());
        assert!(Frame::decode(&b[..63], 0).is_err());
        let mut longer = b.clone();
        longer.push(0);
        assert!(Frame::decode(&longer, 0).is_err());
        assert!(Frame::decode(&b, 1).is_err());
        for (at, value) in [(0, 0), (1, 0), (4, 111), (6, 0), (7, 99)] {
            let mut words = good();
            words[at] = value;
            assert!(Frame::decode(&bytes(words), 0).is_err());
        }
        for (target, status) in [
            (0, 1 << 31),
            (255 << 16, 1 << 31),
            (100 << 16, 65 << 16),
            (50 << 16, (1 << 31) | (127 << 16)),
        ] {
            let mut words = good();
            words[2] = target;
            words[3] = status;
            assert!(
                Frame::decode(&bytes(words), 0)
                    .and_then(|f| f.temperature())
                    .is_err()
            );
        }
    }
    #[test]
    fn only_approved_intel_and_zen3_packages_can_reach_driver() {
        assert_eq!(
            Backend::for_cpu(b"GenuineIntel", 0x906a3, 1 << 6),
            Some(Backend::Intel)
        );
        assert_eq!(
            Backend::for_cpu(b"AuthenticAMD", 0xa20f10, 0),
            Some(Backend::AmdZen3)
        );
        assert_eq!(Backend::for_cpu(b"AuthenticAMD", 0x906a3, 1 << 6), None);
        assert_eq!(Backend::for_cpu(b"GenuineIntel", 0x906a3, 0), None);
        assert_eq!(Backend::for_cpu(b"GenuineIntel", 0x806c1, 1 << 6), None);
        assert_eq!(Backend::for_cpu(b"AuthenticAMD", 0x800f11, 0), None);
        assert_eq!(Backend::for_cpu(b"AuthenticAMD", 0xb40f40, 0), None);
    }

    #[test]
    fn zen3_frames_preserve_fractional_zero_and_corrected_temperatures() -> Result<()> {
        let mut words = good();
        words[0] = AMD_MAGIC;
        words[3] = 0;
        for (raw, expected) in [
            (0, 0.),
            (401 << 21, 50.125),
            ((632 << 21) | (1 << 19), 30.),
            ((632 << 21) | (3 << 16), 30.),
            ((72 << 21) | (1 << 19), -40.),
            (1000 << 21, 125.),
        ] {
            words[2] = raw;
            let frame = Frame::decode(&bytes(words), 0)?;
            assert_eq!(frame.backend, Backend::AmdZen3);
            assert_eq!(frame.temperature()?, expected);
        }
        Ok(())
    }

    #[test]
    fn zen3_frames_reject_foreign_operands_and_impossible_register_values() {
        let mut words = good();
        words[0] = AMD_MAGIC;
        words[2] = 400 << 21;
        // Intel DTS operands must never be accepted under the AMD wire tag.
        assert!(Frame::decode(&bytes(words), 0).is_err());
        words[3] = 0;
        for raw in [
            u64::from(u32::MAX),
            1 << 32,
            1008 << 21,
            (64 << 21) | (1 << 19),
        ] {
            words[2] = raw;
            assert!(Frame::decode(&bytes(words), 0).is_err());
        }
    }

    #[test]
    fn terminal_error_frames_keep_backend_and_specific_failure() -> Result<()> {
        for magic in [MAGIC, AMD_MAGIC] {
            let mut words = good();
            words[0] = magic;
            words[2] = 0;
            words[3] = 0;
            for error in [1, 3, 4, 8] {
                words[7] = error;
                let frame = Frame::decode(&bytes(words), 0)?;
                assert_eq!(frame.temperature(), Err(error_reason(error).into()));
                let (expected, other) = if magic == MAGIC {
                    (Backend::Intel, Backend::AmdZen3)
                } else {
                    (Backend::AmdZen3, Backend::Intel)
                };
                assert!(frame.validate_backend(expected).is_ok());
                assert!(frame.validate_backend(other).is_err());
            }
            words[7] = 9;
            assert!(Frame::decode(&bytes(words), 0).is_err());
        }
        Ok(())
    }
    #[test]
    fn one_package_topology_selects_first_processor_and_rejects_ambiguity() -> Result<()> {
        let mut b = vec![0u8; 48];
        b[..4].copy_from_slice(&3u32.to_le_bytes());
        b[4..8].copy_from_slice(&48u32.to_le_bytes());
        b[30..32].copy_from_slice(&1u16.to_le_bytes());
        b[32..40].copy_from_slice(&0b1100u64.to_le_bytes());
        b[40..42].copy_from_slice(&2u16.to_le_bytes());
        assert_eq!(package_affinity(&b)?, (2, 4));
        let two = [b.clone(), b.clone()].concat();
        assert!(package_affinity(&two).is_err());
        assert!(package_affinity(&b[..47]).is_err());
        b[32..40].fill(0);
        assert!(package_affinity(&b).is_err());
        Ok(())
    }
}
