//! Opt-in, fixed-operation Windows CPU package temperature session.
const HELPER_FLAG: &str = "--system-pulse-cpu-temperature-helper";
#[cfg(target_os = "windows")]
mod driver;
#[cfg(target_os = "windows")]
mod identity;
#[cfg(target_os = "windows")]
mod native;
#[cfg(any(test, target_os = "windows"))]
mod protocol;
#[cfg(any(test, target_os = "windows"))]
mod session;
#[cfg(any(test, target_os = "windows"))]
mod watchdog;
#[cfg(any(test, target_os = "windows"))]
pub(crate) use session::Control;

/// Dispatch before any UI initialization. The iterator includes the executable argument.
pub fn helper_entry(arguments: impl IntoIterator<Item = std::ffi::OsString>) -> Option<i32> {
    let mut args = arguments.into_iter();
    args.next();
    let flag = args.next()?;
    if flag != HELPER_FLAG {
        return None;
    }
    #[cfg(target_os = "windows")]
    {
        let rest: Vec<_> = args.take(4).collect();
        Some(
            match protocol::Request::parse(&rest).and_then(native::helper) {
                Ok(()) => 0,
                Err(_) => 2,
            },
        )
    }
    #[cfg(not(target_os = "windows"))]
    {
        Some(2)
    }
}

#[cfg(target_os = "windows")]
impl Control {
    pub(crate) fn enable(self: &std::sync::Arc<Self>) -> Result<(), String> {
        let Some(generation) = self.begin()? else {
            return Ok(());
        };
        let control = self.clone();
        match std::thread::Builder::new()
            .name("pulse-cpu-temperature".into())
            .spawn(move || native::supervise(control, generation))
        {
            Ok(_) => Ok(()), // Detach: a UAC prompt must never block service/UI drop.
            Err(e) => {
                let reason = format!("Start CPU temperature supervisor: {e}");
                self.finish(generation, reason.clone());
                Err(reason)
            }
        }
    }
}

#[cfg(any(test, target_os = "windows"))]
pub(crate) struct WindowsThermalCollector {
    pub(crate) control: std::sync::Arc<Control>,
}
#[cfg(any(test, target_os = "windows"))]
impl WindowsThermalCollector {
    pub(crate) fn new() -> Self {
        Self {
            control: std::sync::Arc::new(Control::default()),
        }
    }
    pub(crate) fn collect(&self, snapshot: &mut crate::Snapshot, origin: std::time::Instant) {
        use crate::{
            Availability, RawObservation, SensorKind, Unit,
            counters::{measured, missing},
        };
        use session::Latest;
        const ID: &str = "cpu:host/windows-package-temperature";
        let reading = match self.control.latest(std::time::Instant::now()) {
            Latest::Off => missing(
                ID,
                Availability::Unavailable,
                "CPU temperature access is off; enable it to request Windows authorization".into(),
            ),
            Latest::Pending => missing(
                ID,
                Availability::WarmingUp,
                "Waiting for CPU temperature authorization and helper startup".into(),
            ),
            Latest::Failed(reason) => missing(ID, Availability::Failed, reason),
            Latest::Sample(frame, received) => match frame.temperature() {
                Err(reason) => missing(ID, Availability::Failed, reason),
                Ok(value) => {
                    let mut reading = measured(ID, value, None);
                    reading.observations.push(RawObservation {
                        source: "PawnIO 2.2 / signed IntelMSR 0.2.11 / fixed CPU package DTS"
                            .into(),
                        captured_ns: received
                            .saturating_duration_since(origin)
                            .as_nanos()
                            .min(u128::from(u64::MAX)) as u64,
                        read_started_ns: None,
                        integers: [
                            ("helper_sequence", frame.sequence),
                            ("ia32_temperature_target", frame.target),
                            ("ia32_package_therm_status", frame.status),
                            ("query_before_qpc", frame.before),
                            ("query_after_qpc", frame.after),
                            ("query_qpc_frequency", frame.frequency),
                        ]
                        .into_iter()
                        .map(|(k, v)| (k.into(), v))
                        .collect(),
                        decimals: Default::default(),
                    });
                    reading
                }
            },
        };
        crate::host::sensor(
            snapshot,
            "cpu:host",
            "windows-package-temperature",
            "CPU package temperature",
            SensorKind::Temperature,
            Unit::Celsius,
            "PawnIO / Intel package digital thermal sensor",
            "One physical Intel CPU package; not individual cores or ACPI thermal zones",
            reading,
        );
    }
}
#[cfg(any(test, target_os = "windows"))]
impl Drop for WindowsThermalCollector {
    fn drop(&mut self) {
        self.control.disable();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Availability, SensorKind, Snapshot, Unit};
    use std::time::{Duration, Instant};
    #[test]
    fn off_and_pending_are_present_without_an_invented_zero() {
        let collector = WindowsThermalCollector::new();
        let origin = Instant::now();
        let mut s = Snapshot::default();
        collector.collect(&mut s, origin);
        assert_eq!(s.sensors.len(), 1);
        assert_eq!(s.sensors[0].id, "cpu:host/windows-package-temperature");
        assert_eq!(s.readings[0].availability, Availability::Unavailable);
        assert_eq!(s.readings[0].value, None);
        collector.control.begin().unwrap();
        let mut s = Snapshot::default();
        collector.collect(&mut s, origin);
        assert_eq!(s.readings[0].availability, Availability::WarmingUp);
        assert_eq!(s.readings[0].value, None);
    }
    #[test]
    fn measured_package_uses_receipt_origin_and_retains_separate_qpc() {
        let collector = WindowsThermalCollector::new();
        let origin = Instant::now() - Duration::from_millis(10);
        let received = Instant::now();
        let generation = collector.control.begin().unwrap().unwrap();
        collector.control.publish(
            generation,
            session::Latest::Sample(
                protocol::Frame {
                    sequence: 1,
                    target: 100 << 16,
                    status: (1 << 31) | (65 << 16),
                    before: 999999,
                    after: 1000000,
                    frequency: 10000000,
                    error: 0,
                },
                received,
            ),
        );
        let mut s = Snapshot::default();
        collector.collect(&mut s, origin);
        assert_eq!(s.readings.len(), 1);
        let r = &s.readings[0];
        assert_eq!(r.value, Some(35.0));
        assert_eq!(s.sensors[0].kind, SensorKind::Temperature);
        assert_eq!(s.sensors[0].unit, Unit::Celsius);
        let o = &r.observations[0];
        assert_eq!(o.integers["query_before_qpc"], 999999);
        assert_eq!(o.read_started_ns, None);
        assert_eq!(
            o.captured_ns,
            received.duration_since(origin).as_nanos() as u64
        );
        collector.control.disable();
        let mut s = Snapshot::default();
        collector.collect(&mut s, origin);
        assert!(s.readings[0].value.is_none());
    }
    #[test]
    fn helper_mode_is_exact_and_rejects_malformed_requests() {
        assert_eq!(helper_entry(["pulse", "--other"].map(Into::into)), None);
        assert_eq!(
            helper_entry(["pulse", "--system-pulse-cpu-temperature-helper"].map(Into::into)),
            Some(2)
        );
    }
}
