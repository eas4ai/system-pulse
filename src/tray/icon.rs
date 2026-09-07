//! A fixed-scale aggregate CPU history, readable at native panel-icon sizes.
use system_pulse_model::Sample;

pub(super) const SIZE: usize = 32;
const LEFT: usize = 2;
const RIGHT: usize = SIZE - 3;
const TOP: usize = 2;
const BOTTOM: usize = SIZE - 3;
const BACKGROUND: [u8; 4] = [17, 25, 17, 255];
const GRID: [u8; 4] = [30, 47, 28, 255];
const BORDER: [u8; 4] = [78, 113, 62, 255];
const MISSING: [u8; 4] = [224, 164, 62, 255];
const FILL: [u8; 4] = [46, 86, 31, 255];
const LINE: [u8; 4] = [143, 215, 83, 255];

#[derive(Clone, PartialEq, Eq)]
pub(super) struct Frame {
    pub pixels: Vec<u8>,
    pub tooltip: String,
}

fn current(sample: &Sample) -> Option<f64> {
    sample
        .chart_value()
        .filter(|value| value.is_finite())
        .map(|value| value.clamp(0., 100.))
}

fn pixel(pixels: &mut [u8], x: usize, y: usize, color: [u8; 4]) {
    let offset = (y * SIZE + x) * 4;
    pixels[offset..offset + 4].copy_from_slice(&color);
}

fn column(pixels: &mut [u8], x: usize, y: usize) {
    for row in y..=BOTTOM {
        pixel(pixels, x, row, FILL);
    }
    pixel(pixels, x, y, LINE);
}

pub(super) fn render(samples: &[Sample]) -> Frame {
    let mut pixels = BACKGROUND.repeat(SIZE * SIZE);
    let border = if samples.last().and_then(current).is_some() {
        BORDER
    } else {
        MISSING
    };
    for axis in 0..SIZE {
        for edge in [0, SIZE - 1] {
            pixel(&mut pixels, axis, edge, border);
            pixel(&mut pixels, edge, axis, border);
        }
    }
    for y in (TOP..=BOTTOM).step_by(7) {
        for x in LEFT..=RIGHT {
            pixel(&mut pixels, x, y, GRID);
        }
    }
    // At most one retained observation per drawable column. Relative capture
    // times position observations; a missing reading breaks the trace.
    let samples = &samples[samples.len().saturating_sub(RIGHT - LEFT + 1)..];
    let first = samples.first().map_or(0, |sample| sample.at_ms);
    let last = samples.last().map_or(first, |sample| sample.at_ms);
    let span = last.saturating_sub(first);
    let mut previous: Option<(usize, usize)> = None;
    let mut previous_time = None;
    for sample in samples {
        let monotonic = previous_time.is_none_or(|time| sample.at_ms > time);
        previous_time = Some(sample.at_ms);
        let Some(value) = current(sample).filter(|_| monotonic) else {
            previous = None;
            continue;
        };
        let x = if span == 0 {
            RIGHT
        } else {
            LEFT + ((sample.at_ms.saturating_sub(first) as f64 / span as f64).clamp(0., 1.)
                * (RIGHT - LEFT) as f64)
                .round() as usize
        };
        let y = BOTTOM - (value / 100. * (BOTTOM - TOP) as f64).round() as usize;
        if let Some((px, py)) = previous.filter(|(px, _)| *px < x) {
            for column_x in px..=x {
                let ratio = (column_x - px) as f64 / (x - px) as f64;
                let column_y = (py as f64 + (y as f64 - py as f64) * ratio).round() as usize;
                column(&mut pixels, column_x, column_y);
            }
        }
        column(&mut pixels, x, y);
        previous = Some((x, y));
    }
    let tooltip = match samples.last().and_then(current) {
        Some(value) => format!("System Pulse · CPU {value:.1}%"),
        None => format!(
            "System Pulse · CPU {}",
            crate::meters::value(samples.last())
        ),
    };
    Frame { pixels, tooltip }
}

#[cfg(test)]
mod tests {
    use super::*;
    use system_pulse_model::{Quantity, ReadingStatus};

    fn sample(at_ms: u64, value: Option<f64>, status: ReadingStatus) -> Sample {
        Sample {
            at_ms,
            value,
            status,
            quantity: Quantity::Percentage,
            total: None,
            unit: "%".into(),
            text: String::new(),
            reason: None,
        }
    }
    fn at(frame: &Frame, x: usize, y: usize) -> &[u8] {
        &frame.pixels[(y * SIZE + x) * 4..(y * SIZE + x + 1) * 4]
    }

    #[test]
    fn zero_and_full_load_use_fixed_scale_and_exact_tooltip() {
        let zero = render(&[sample(1, Some(0.), ReadingStatus::Current)]);
        let full = render(&[sample(1, Some(100.), ReadingStatus::Current)]);
        assert_eq!(zero.pixels.len(), SIZE * SIZE * 4);
        assert_eq!(at(&zero, RIGHT, BOTTOM), LINE);
        assert_eq!(at(&full, RIGHT, TOP), LINE);
        assert_eq!(zero.tooltip, "System Pulse · CPU 0.0%");
        assert_eq!(full.tooltip, "System Pulse · CPU 100.0%");
    }

    #[test]
    fn missing_and_stale_are_not_idle_and_break_the_trace() {
        let missing = render(&[sample(1, None, ReadingStatus::Unavailable)]);
        let stale = render(&[sample(1, Some(50.), ReadingStatus::Stale)]);
        assert_eq!(at(&missing, 0, 0), MISSING);
        assert_eq!(at(&stale, 0, 0), MISSING);
        assert!(stale.tooltip.contains("Stale"));
        assert!(!missing.pixels.chunks_exact(4).any(|p| p == LINE));
        let gap = render(&[
            sample(0, Some(50.), ReadingStatus::Current),
            sample(1, None, ReadingStatus::Failed),
            sample(2, Some(50.), ReadingStatus::Current),
        ]);
        assert!((TOP..=BOTTOM).all(|y| at(&gap, 16, y) != LINE && at(&gap, 16, y) != FILL));
    }

    #[test]
    fn history_is_bounded_and_nonfinite_never_becomes_a_measurement() {
        let samples: Vec<_> = (0..1000)
            .map(|at| sample(at, Some((at % 101) as f64), ReadingStatus::Current))
            .collect();
        assert_eq!(
            render(&samples).pixels,
            render(&samples[samples.len() - 28..]).pixels
        );
        let invalid = render(&[sample(1, Some(f64::NAN), ReadingStatus::Current)]);
        assert_eq!(at(&invalid, 0, 0), MISSING);
        assert!(!invalid.pixels.chunks_exact(4).any(|p| p == LINE));
    }
}
