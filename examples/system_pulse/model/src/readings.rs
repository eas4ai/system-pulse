use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, VecDeque};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReadingStatus {
    Current,
    Stale,
    Unavailable,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Sample {
    /// Milliseconds on one session's monotonic fixture/collector clock.
    pub at_ms: u64,
    /// Optional scalar for the chosen chart; text can describe compound values.
    pub value: Option<f64>,
    pub text: String,
    pub unit: String,
    pub status: ReadingStatus,
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
        if self.status == ReadingStatus::Unavailable && self.value.is_some() {
            return Err("Unavailable reading cannot contain a measured value".into());
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

    pub fn latest(&self, monitor: &str, sensor: &str) -> Option<&Sample> {
        self.samples(monitor, sensor)
            .and_then(|series| series.back())
    }

    pub fn samples(&self, monitor: &str, sensor: &str) -> Option<&VecDeque<Sample>> {
        self.series.get(&(monitor.to_owned(), sensor.to_owned()))
    }
}
