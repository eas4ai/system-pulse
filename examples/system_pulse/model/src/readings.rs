use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReadingStatus {
    Current,
    Stale,
    Unavailable,
    WarmingUp,
    Failed,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Sample {
    /// Milliseconds on one session's monotonic collector clock.
    pub at_ms: u64,
    /// Optional scalar for the chosen chart; text can describe compound values.
    pub value: Option<f64>,
    pub text: String,
    pub unit: String,
    pub status: ReadingStatus,
    #[serde(default)]
    pub quantity: Quantity,
    #[serde(default)]
    pub total: Option<f64>,
    #[serde(default)]
    pub reason: Option<String>,
}

impl Sample {
    pub fn chart_value(&self) -> Option<f64> {
        if self.status == ReadingStatus::Current {
            self.value
        } else {
            None
        }
    }

    fn validate(&self) -> Result<(), String> {
        if self.value.is_some_and(|value| !value.is_finite()) {
            return Err("Reading contains a non-finite chart value".into());
        }
        if !matches!(self.status, ReadingStatus::Current | ReadingStatus::Stale)
            && self.value.is_some()
        {
            return Err("Unavailable reading cannot contain a measured value".into());
        }
        if self.value.is_some_and(|v| v < 0.) && self.quantity != Quantity::Temperature {
            return Err("Negative value for a nonnegative quantity".into());
        }
        if self.total.is_some_and(|v| !v.is_finite() || v < 0.) {
            return Err("Capacity total must be nonnegative and finite".into());
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct HistoryStore {
    capacity: usize,
    series: BTreeMap<(String, String), VecDeque<Sample>>,
}

impl HistoryStore {
    pub fn new(capacity: usize) -> Result<Self, String> {
        if !(1..=3600).contains(&capacity) {
            return Err("History capacity must be between 1 and 3600 samples".into());
        }
        Ok(Self {
            capacity,
            series: BTreeMap::new(),
        })
    }

    pub fn push(&mut self, monitor: &str, sensor: &str, sample: Sample) -> Result<(), String> {
        if monitor.trim().is_empty() || sensor.trim().is_empty() {
            return Err("Reading requires stable monitor and sensor identities".into());
        }
        sample.validate()?;
        let key = (monitor.to_owned(), sensor.to_owned());
        if self
            .series
            .get(&key)
            .and_then(|series| series.back())
            .is_some_and(|previous| sample.at_ms <= previous.at_ms)
        {
            return Err("Reading timestamps must increase within each series".into());
        }
        let series = self.series.entry(key).or_default();
        if series.len() == self.capacity {
            series.pop_front();
        }
        series.push_back(sample);
        Ok(())
    }

    pub fn retain_keys(&mut self, keys: &BTreeSet<(String, String)>) {
        self.series.retain(|key, _| keys.contains(key));
    }

    pub fn series_count(&self) -> usize {
        self.series.len()
    }

    /// Age the latest observation in place; timers never manufacture history points.
    pub fn mark_stale(&mut self, now_ms: u64, threshold_ms: u64) -> bool {
        let mut changed = false;
        for series in self.series.values_mut() {
            if let Some(last) = series.back_mut() {
                if last.status == ReadingStatus::Current
                    && now_ms.saturating_sub(last.at_ms) > threshold_ms
                {
                    last.status = ReadingStatus::Stale;
                    changed = true;
                }
            }
        }
        changed
    }

    pub fn latest(&self, monitor: &str, sensor: &str) -> Option<&Sample> {
        self.samples(monitor, sensor)
            .and_then(|series| series.back())
    }

    pub fn samples(&self, monitor: &str, sensor: &str) -> Option<&VecDeque<Sample>> {
        self.series.get(&(monitor.to_owned(), sensor.to_owned()))
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Quantity {
    #[default]
    Percentage,
    Temperature,
    Rate,
    Capacity,
    Counter,
    Frequency,
    Power,
    Duration,
    Scalar,
}
impl Quantity {
    pub fn meters(self) -> &'static [crate::Meter] {
        use crate::Meter::*;
        match self {
            Self::Percentage => &[Number, Line, Bar, Sparkline, Radial],
            Self::Temperature => &[Number, Sparkline, Line, Radial],
            Self::Rate | Self::Frequency | Self::Power | Self::Scalar => &[Number, Sparkline, Line],
            Self::Capacity => &[Number, Bar],
            Self::Counter => &[Number, Sparkline],
            Self::Duration => &[Number, Sparkline, Line],
        }
    }
    pub fn compatible(self, meter: crate::Meter) -> crate::Meter {
        if self.meters().contains(&meter) {
            meter
        } else {
            crate::Meter::Number
        }
    }
    pub fn next_meter(self, meter: crate::Meter) -> crate::Meter {
        let meters = self.meters();
        meters[meters
            .iter()
            .position(|m| *m == meter)
            .map_or(0, |i| (i + 1) % meters.len())]
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum PhysicalUnit {
    Percent,
    Bytes,
    BytesPerSecond,
    Celsius,
    Hertz,
    Watts,
    Rpm,
    Count,
    CountPerSecond,
    Milliseconds,
    Seconds,
    Load,
}
impl PhysicalUnit {
    pub fn symbol(self) -> &'static str {
        match self {
            Self::Percent => "%",
            Self::Bytes => "B",
            Self::BytesPerSecond => "B/s",
            Self::Celsius => "°C",
            Self::Hertz => "Hz",
            Self::Watts => "W",
            Self::Rpm => "RPM",
            Self::Count => "count",
            Self::CountPerSecond => "count/s",
            Self::Milliseconds => "ms",
            Self::Seconds => "s",
            Self::Load => "load",
        }
    }
    fn scale(self, value: f64) -> (f64, String) {
        let (base, prefixes): (f64, &[&str]) = match self {
            Self::Bytes | Self::BytesPerSecond => (1024., &["", "Ki", "Mi", "Gi", "Ti", "Pi"]),
            Self::Hertz => (1000., &["", "k", "M", "G", "T"]),
            _ => return (1., self.symbol().into()),
        };
        let mut divisor = 1.;
        let mut index = 0;
        while value.abs() / divisor >= base && index + 1 < prefixes.len() {
            divisor *= base;
            index += 1;
        }
        (divisor, format!("{}{}", prefixes[index], self.symbol()))
    }
}
impl Sample {
    pub fn measured(
        at_ms: u64,
        quantity: Quantity,
        value: f64,
        total: Option<f64>,
        physical_unit: PhysicalUnit,
    ) -> Result<Self, String> {
        let (divisor, unit) = physical_unit.scale(total.unwrap_or(value));
        let text = if let Some(total) = total {
            format!("{:.1} / {:.1}", value / divisor, total / divisor)
        } else if matches!(physical_unit, PhysicalUnit::Count | PhysicalUnit::Rpm) {
            format!("{value:.0}")
        } else {
            format!("{:.1}", value / divisor)
        };
        let sample = Self {
            at_ms,
            quantity,
            value: Some(value),
            total,
            text,
            unit,
            status: ReadingStatus::Current,
            reason: None,
        };
        sample.validate()?;
        Ok(sample)
    }
    pub fn capacity_ratio(&self) -> Option<f64> {
        if self.quantity != Quantity::Capacity {
            return None;
        }
        let total = self.total.filter(|total| *total > 0.)?;
        Some(self.chart_value()? / total)
    }
}

/// Physical chart coordinates. Temperature uses an explicitly labelled observed range,
/// never an invented safe operating range. Percentages may exceed 100 (e.g. NVML fan).
pub fn chart_range(samples: &[Sample]) -> (f64, f64) {
    let quantity = samples.last().map(|s| s.quantity).unwrap_or_default();
    let mut values = samples.iter().filter_map(Sample::chart_value);
    let Some(first) = values.next() else {
        return (0., 1.);
    };
    let (mut low, mut high) = values.fold((first, first), |(low, high), value| {
        (low.min(value), high.max(value))
    });
    if quantity != Quantity::Temperature {
        low = 0.;
    }
    if quantity == Quantity::Percentage {
        high = high.max(100.);
    }
    if high <= low {
        low -= if quantity == Quantity::Temperature {
            1.
        } else {
            0.
        };
        high += 1.;
    }
    (low, high)
}

/// Horizontal coordinate on elapsed snapshot capture time, independent of cadence.
pub fn chart_x(samples: &[Sample], index: usize) -> f32 {
    let Some(first) = samples.first() else {
        return 0.;
    };
    let Some(last) = samples.last() else {
        return 0.;
    };
    let Some(sample) = samples.get(index) else {
        return 0.;
    };
    sample.at_ms.saturating_sub(first.at_ms) as f32
        / last.at_ms.saturating_sub(first.at_ms).max(1) as f32
}
