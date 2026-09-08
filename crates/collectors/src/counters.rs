//! Bounded baselines keyed by stable source identity; failed reads invalidate continuity.
use crate::types::*;
use std::collections::BTreeMap;
struct Baseline {
    observation: RawObservation,
    touched: bool,
}
#[derive(Default)]
pub struct Counters {
    baselines: BTreeMap<String, Baseline>,
}
impl Counters {
    pub fn rate(&mut self, key: &str, value: Result<u64, String>, ns: u64) -> Option<f64> {
        let reading = self.derive(
            key,
            value.map(|v| raw(key, ns, [("value", v)])),
            |a, b, elapsed| Ok(delta(a, b, "value")? as f64 / elapsed),
        );
        reading.value
    }
    pub fn retain(&mut self, keys: &[&str]) {
        self.baselines.retain(|k, _| keys.contains(&k.as_str()));
    }
    pub fn len(&self) -> usize {
        self.baselines.len()
    }
    pub fn is_empty(&self) -> bool {
        self.baselines.is_empty()
    }
    pub(crate) fn begin(&mut self) {
        for baseline in self.baselines.values_mut() {
            baseline.touched = false;
        }
    }
    pub(crate) fn finish(&mut self) {
        self.baselines.retain(|_, baseline| baseline.touched);
    }
    pub(crate) fn derive(
        &mut self,
        key: &str,
        observation: Result<RawObservation, String>,
        formula: impl FnOnce(&RawObservation, &RawObservation, f64) -> Result<f64, String>,
    ) -> Reading {
        let current = match observation {
            Ok(o) => o,
            Err(e) => {
                self.baselines.remove(key);
                return missing(key, Availability::Failed, e);
            }
        };
        let previous = if let Some(baseline) = self.baselines.get_mut(key) {
            baseline.touched = true;
            Some(std::mem::replace(
                &mut baseline.observation,
                current.clone(),
            ))
        } else {
            self.baselines.insert(
                key.into(),
                Baseline {
                    observation: current.clone(),
                    touched: true,
                },
            );
            None
        };
        let Some(previous) = previous else {
            let mut r = missing(
                key,
                Availability::WarmingUp,
                "Waiting for a second counter observation".into(),
            );
            r.observations.push(current);
            return r;
        };
        let elapsed = current
            .captured_ns
            .checked_sub(previous.captured_ns)
            .filter(|v| *v > 0);
        let result = elapsed
            .ok_or_else(|| "Nonpositive monotonic elapsed time".to_string())
            .and_then(|ns| formula(&previous, &current, ns as f64 / 1e9));
        let mut r = match result {
            Ok(v) if v.is_finite() && v >= 0.0 => measured(key, v, None),
            Ok(_) => missing(
                key,
                Availability::Failed,
                "Invalid non-finite or negative delta result".into(),
            ),
            Err(e) => missing(key, Availability::WarmingUp, e),
        };
        r.observations = vec![previous, current];
        r
    }
}
pub(crate) fn raw<const N: usize>(
    source: &str,
    ns: u64,
    values: [(&str, u64); N],
) -> RawObservation {
    RawObservation {
        source: source.into(),
        captured_ns: ns,
        read_started_ns: None,
        integers: values.into_iter().map(|(k, v)| (k.into(), v)).collect(),
        decimals: BTreeMap::new(),
    }
}
pub(crate) fn raw_window<const N: usize>(
    source: &str,
    start: u64,
    end: u64,
    values: [(&str, u64); N],
) -> RawObservation {
    let mut observation = raw(source, end, values);
    observation.read_started_ns = Some(start);
    observation
}
pub(crate) fn delta(a: &RawObservation, b: &RawObservation, key: &str) -> Result<u64, String> {
    b.integers
        .get(key)
        .zip(a.integers.get(key))
        .and_then(|(b, a)| b.checked_sub(*a))
        .ok_or_else(|| format!("Counter {key} missing or decreased; baseline reset"))
}
pub(crate) fn measured(id: &str, value: f64, total: Option<f64>) -> Reading {
    Reading {
        sensor_id: id.into(),
        value: Some(value),
        total,
        availability: Availability::Available,
        reason: None,
        observations: Vec::new(),
    }
}
pub(crate) fn missing(id: &str, availability: Availability, reason: String) -> Reading {
    Reading {
        sensor_id: id.into(),
        value: None,
        total: None,
        availability,
        reason: Some(reason),
        observations: Vec::new(),
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn measured_irregular_elapsed() {
        let mut c = Counters::default();
        assert_eq!(c.rate("rx", Ok(1000), 1_000_000_000), None);
        assert_eq!(c.rate("rx", Ok(4000), 2_500_000_000), Some(2000.0));
    }
    #[test]
    fn reset_zero_elapsed_and_failed_read_reset_baseline() {
        let mut c = Counters::default();
        c.rate("rx", Ok(100), 1);
        assert_eq!(c.rate("rx", Ok(200), 1), None);
        assert_eq!(c.rate("rx", Ok(0), 2), None);
        assert_eq!(c.rate("rx", Err("denied".into()), 3), None);
        assert_eq!(c.rate("rx", Ok(1000), 1_000_000_000), None);
        assert_eq!(c.rate("rx", Ok(3000), 2_000_000_000), Some(2000.0));
    }
    #[test]
    fn reorder_removal_and_reappearance() {
        let mut c = Counters::default();
        c.rate("a", Ok(100), 1_000_000_000);
        c.rate("b", Ok(500), 1_000_000_000);
        assert_eq!(c.rate("b", Ok(900), 2_000_000_000), Some(400.0));
        assert_eq!(c.rate("a", Ok(200), 2_000_000_000), Some(100.0));
        c.retain(&["b"]);
        assert_eq!(c.len(), 1);
        assert_eq!(c.rate("a", Ok(1000), 3_000_000_000), None);
    }

    #[test]
    fn public_retain_releases_all_identity_state_during_churn() {
        let mut counters = Counters::default();
        for index in 0..1000 {
            counters.rate(&format!("interface-{index}"), Ok(10), 1);
            counters.retain(&[]);
            assert!(counters.is_empty());
        }
    }

    #[test]
    fn capture_eviction_preserves_only_fresh_successful_baselines() {
        let mut counters = Counters::default();
        counters.begin();
        counters.rate("a", Ok(10), 1_000_000_000);
        counters.rate("b", Ok(20), 1_000_000_000);
        counters.rate("c", Ok(30), 1_000_000_000);
        counters.finish();
        counters.begin();
        assert_eq!(counters.rate("b", Ok(40), 2_000_000_000), Some(20.0));
        assert_eq!(
            counters.rate("c", Err("removed".into()), 2_000_000_000),
            None
        );
        counters.finish();
        assert_eq!(counters.len(), 1);
        counters.begin();
        assert_eq!(counters.rate("c", Ok(60), 3_000_000_000), None);
        assert_eq!(counters.rate("a", Ok(30), 3_000_000_000), None);
        assert_eq!(counters.rate("b", Ok(70), 3_000_000_000), Some(30.0));
        counters.finish();
        assert_eq!(counters.len(), 3);
        counters.begin();
        counters.finish();
        assert!(counters.is_empty());
    }
}
