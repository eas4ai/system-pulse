use crate::meters;
use gpui_kit::component::ActiveTheme;
use gpui_kit::*;
use system_pulse_model::{HistoryStore, MonitorDescriptor, Quantity};

pub(crate) fn memory_segments(history: &HistoryStore) -> Option<[f64; 4]> {
    let total = history.latest("memory:host", "memory:host/total")?;
    let bytes = total.chart_value().filter(|v| v.is_finite() && *v > 0.)?;
    if total.quantity != Quantity::Capacity {
        return None;
    }
    let mut values = [0.; 4];
    for (index, id) in ["other", "cache", "buffers", "free"]
        .into_iter()
        .enumerate()
    {
        let sample = history.latest("memory:host", &format!("memory:host/{id}"))?;
        if sample.at_ms != total.at_ms || sample.quantity != Quantity::Capacity {
            return None;
        }
        values[index] = sample.chart_value().filter(|v| v.is_finite() && *v >= 0.)?;
    }
    if (values.iter().sum::<f64>() - bytes).abs() > (bytes * 1e-9).max(1.) {
        return None;
    }
    Some(values.map(|value| value / bytes))
}

pub(crate) fn core_number(id: &str) -> Option<u32> {
    id.strip_prefix("cpu:host/core-")?
        .strip_suffix("-usage")?
        .parse()
        .ok()
}

pub(crate) fn hero(
    monitor: &MonitorDescriptor,
    history: &HistoryStore,
    cx: &App,
) -> Option<AnyElement> {
    if monitor.summary.is_empty()
        || !(matches!(monitor.id.as_str(), "cpu:host" | "memory:host")
            || crate::layout::is_gpu(&monitor.id))
    {
        return None;
    }
    let sample = meters::summary_sample(monitor, history);
    let label = meters::value(sample.as_ref());
    let measured = sample.as_ref().is_some_and(|sample| sample.value.is_some());
    Some(
        div()
            .px_3()
            .py_2()
            .flex()
            .flex_col()
            .gap_1()
            .child(
                div()
                    .text_sm()
                    .text_color(cx.theme().muted_foreground)
                    .child(if monitor.id == "memory:host" {
                        "Memory in use"
                    } else {
                        "Utilization"
                    }),
            )
            .child(
                meters::metric_label(format!("{}:hero", monitor.id), label)
                    .font_family(cx.theme().mono_font_family.clone())
                    .text_size(px(if measured { 26. } else { 14. })),
            )
            .into_any_element(),
    )
}

pub(crate) fn memory_composition(history: &HistoryStore, cx: &App) -> AnyElement {
    let Some(parts) = memory_segments(history) else {
        return div()
            .px_3()
            .py_2()
            .text_sm()
            .text_color(cx.theme().muted_foreground)
            .child("Memory composition unavailable for the current observation.")
            .into_any_element();
    };
    let colors = [0x38bdf8, 0x2dd4bf, 0xfbbf24, 0x64748b];
    let labels = ["Other", "Cache", "Buffers", "Free"];
    let ids = ["other", "cache", "buffers", "free"];
    let legend = (0..4).map(|index| {
        let text =
            meters::value(history.latest("memory:host", &format!("memory:host/{}", ids[index])));
        div()
            .flex()
            .items_center()
            .gap_1()
            .text_sm()
            .child(div().size_2().bg(rgb(colors[index])))
            .child(labels[index])
            .child(
                div()
                    .font_family(cx.theme().mono_font_family.clone())
                    .child(text),
            )
    });
    div()
        .id("memory-composition")
        .px_3()
        .py_2()
        .flex()
        .flex_col()
        .gap_2()
        .debug_selector(|| "memory:composition".into())
        .child(
            div()
                .w_full()
                .h_3()
                .flex()
                .overflow_hidden()
                .rounded_sm()
                .children((0..4).map(|index| {
                    div()
                        .h_full()
                        .w(relative(parts[index] as f32))
                        .flex_none()
                        .bg(rgb(colors[index]))
                })),
        )
        .child(div().flex().flex_wrap().gap_2().children(legend))
        .into_any_element()
}
#[cfg(test)]
mod tests {
    use super::*;
    use system_pulse_model::{Quantity, ReadingStatus, Sample};
    fn sample(value: f64, at_ms: u64) -> Sample {
        Sample {
            at_ms,
            value: Some(value),
            text: value.to_string(),
            unit: "B".into(),
            quantity: Quantity::Capacity,
            total: None,
            reason: None,
            status: ReadingStatus::Current,
        }
    }
    fn history() -> HistoryStore {
        let mut history = HistoryStore::new(4).unwrap();
        for (id, value) in [
            ("total", 1000.),
            ("other", 600.),
            ("cache", 250.),
            ("buffers", 50.),
            ("free", 100.),
        ] {
            history
                .push(
                    "memory:host",
                    &format!("memory:host/{id}"),
                    sample(value, 1),
                )
                .unwrap();
        }
        history
    }
    #[::core::prelude::v1::test]
    fn memory_composition_uses_disjoint_physical_bytes_and_rejects_incoherent_samples() {
        let mut history = history();
        assert_eq!(memory_segments(&history), Some([0.6, 0.25, 0.05, 0.1]));
        history
            .push("memory:host", "memory:host/free", sample(200., 2))
            .unwrap();
        assert!(
            memory_segments(&history).is_none(),
            "different observation times must not compose"
        );
        history.mark_stale(100, 2);
        assert!(
            memory_segments(&history).is_none(),
            "stale bytes must not look current"
        );
        assert!(memory_segments(&HistoryStore::new(1).unwrap()).is_none());
    }
}
