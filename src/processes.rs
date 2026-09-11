//! Presentation-only process ordering. OS actions remain in the collector crate.
use crate::live::ProcessView;

// Canonical collector columns keep their meaning when presentation hides one.
pub(crate) const VISIBLE_PROCESS_COLUMNS: &[usize] = &[0, 1, 2, 3, 4, 5, 7];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct ProcessSort {
    pub(crate) column: usize,
    pub(crate) descending: bool,
}

impl Default for ProcessSort {
    fn default() -> Self {
        Self {
            column: 2,
            descending: true,
        }
    }
}

impl ProcessSort {
    pub(crate) fn select(&mut self, column: usize) {
        if !VISIBLE_PROCESS_COLUMNS.contains(&column) {
            return;
        }
        if self.column == column {
            self.descending = !self.descending;
        } else {
            self.column = column;
            self.descending = (2..7).contains(&column);
        }
    }
}

pub(crate) fn project(rows: &[ProcessView], query: &str, sort: ProcessSort) -> Vec<usize> {
    use std::cmp::Ordering;
    let query = query.trim().to_lowercase();
    let mut indices: Vec<_> = rows
        .iter()
        .enumerate()
        .filter_map(|(index, row)| {
            (query.is_empty()
                || [0, 1, 7].into_iter().any(|column| {
                    row.cells
                        .get(column)
                        .is_some_and(|text| text.to_lowercase().contains(&query))
                }))
            .then_some(index)
        })
        .collect();
    let text_keys: Vec<_> = if matches!(sort.column, 1 | 7) {
        rows.iter()
            .map(|row| {
                row.cells
                    .get(sort.column)
                    .map(|text| text.to_lowercase())
                    .unwrap_or_default()
            })
            .collect()
    } else {
        Vec::new()
    };
    indices.sort_by(|&a, &b| {
        let order = match sort.column {
            1 | 7 => {
                let order = text_keys[a].cmp(&text_keys[b]);
                if sort.descending {
                    order.reverse()
                } else {
                    order
                }
            }
            2..=6 => {
                let a = rows[a].numeric[sort.column - 2].filter(|value| value.is_finite());
                let b = rows[b].numeric[sort.column - 2].filter(|value| value.is_finite());
                match (a, b) {
                    (Some(a), Some(b)) => {
                        if sort.descending {
                            b.total_cmp(&a)
                        } else {
                            a.total_cmp(&b)
                        }
                    }
                    (Some(_), None) => Ordering::Less,
                    (None, Some(_)) => Ordering::Greater,
                    (None, None) => Ordering::Equal,
                }
            }
            _ => {
                let order = rows[a].identity.pid.cmp(&rows[b].identity.pid);
                if sort.descending {
                    order.reverse()
                } else {
                    order
                }
            }
        };
        order.then_with(|| rows[a].identity.cmp(&rows[b].identity))
    });
    indices
}

#[cfg(test)]
mod tests {
    use super::*;
    use system_pulse_collectors::ProcessIdentity;

    fn row(pid: u32, name: &str, user: &str, cpu: Option<f64>, memory: Option<f64>) -> ProcessView {
        ProcessView {
            identity: ProcessIdentity {
                pid,
                start_time_ticks: u64::from(pid),
            },
            cells: vec![
                pid.to_string(),
                name.into(),
                "formatted CPU".into(),
                "formatted memory".into(),
                String::new(),
                String::new(),
                String::new(),
                user.into(),
            ],
            numeric: [cpu, memory, Some(1.), Some(2.), Some(3.)],
        }
    }

    #[test]
    fn numeric_sort_uses_raw_values_and_keeps_missing_last_in_both_directions() {
        let rows = vec![
            row(1, "a", "user", Some(9.), Some(1024.)),
            row(2, "b", "user", Some(80.), Some(100.)),
            row(3, "c", "user", None, None),
        ];
        assert_eq!(project(&rows, "", ProcessSort::default()), vec![1, 0, 2]);
        assert_eq!(
            project(
                &rows,
                "",
                ProcessSort {
                    column: 2,
                    descending: false
                }
            ),
            vec![0, 1, 2]
        );
        assert_eq!(
            project(
                &rows,
                "",
                ProcessSort {
                    column: 3,
                    descending: true
                }
            ),
            vec![0, 1, 2]
        );
        assert_eq!(
            project(
                &rows,
                "",
                ProcessSort {
                    column: 3,
                    descending: false
                }
            ),
            vec![1, 0, 2]
        );
    }

    #[test]
    fn search_matches_name_pid_and_user_without_changing_source_identities() {
        let rows = vec![
            row(42, "Firefox", "shawn", Some(1.), None),
            row(9, "terminal", "Alice", Some(2.), None),
        ];
        for query in ["FIREFOX", "42", "ShAwN"] {
            assert_eq!(project(&rows, query, ProcessSort::default()), vec![0]);
        }
        assert_eq!(project(&rows, "alice", ProcessSort::default()), vec![1]);
        assert!(project(&rows, "absent", ProcessSort::default()).is_empty());
        assert_eq!(rows[0].identity.pid, 42);
    }

    #[test]
    fn equal_values_have_stable_identity_ties_and_every_column_can_sort() {
        let rows = vec![
            row(42, "Alpha", "zed", Some(1.), Some(1.)),
            row(9, "beta", "alice", Some(1.), Some(1.)),
        ];
        assert_eq!(project(&rows, "", ProcessSort::default()), vec![1, 0]);
        assert_eq!(
            project(
                &rows,
                "",
                ProcessSort {
                    column: 1,
                    descending: false
                }
            ),
            vec![0, 1]
        );
        assert_eq!(
            project(
                &rows,
                "",
                ProcessSort {
                    column: 7,
                    descending: false
                }
            ),
            vec![1, 0]
        );
        let mut sort = ProcessSort::default();
        for &column in VISIBLE_PROCESS_COLUMNS {
            sort.select(column);
            assert_eq!(sort.column, column);
        }
        sort.select(7);
        assert!(sort.descending);
        sort.select(8);
        assert_eq!(sort.column, 7);
    }

    #[test]
    fn platform_columns_keep_user_sort_and_reject_hidden_choices() {
        let expected: &[usize] = &[0, 1, 2, 3, 4, 5, 7];
        assert_eq!(VISIBLE_PROCESS_COLUMNS, expected);
        let mut sort = ProcessSort::default();
        sort.select(6);
        assert_eq!(sort.column, 2);
        sort.select(7);
        assert_eq!(sort.column, 7);
        assert!(!sort.descending);
    }
}
