//! Retain the native discovery connection, never a successful reading after failure.

pub(super) trait TemperatureBackend: Default {
    fn reconnect(&mut self);
    fn refresh_and_remove_absent(&mut self);
    fn needs_reconnect(&self) -> bool;
}

impl TemperatureBackend for sysinfo::Components {
    fn reconnect(&mut self) {
        *self = Self::default();
    }

    fn refresh_and_remove_absent(&mut self) {
        self.refresh(true);
    }

    fn needs_reconnect(&self) -> bool {
        self.is_empty()
            || self
                .iter()
                .any(|component| component.temperature().is_none())
    }
}

#[derive(Default)]
pub(super) struct TemperatureInventory<T = sysinfo::Components> {
    backend: T,
    reconnect: bool,
}

impl<T: TemperatureBackend> TemperatureInventory<T> {
    pub(super) fn refresh(&mut self) -> &T {
        if self.reconnect {
            self.backend.reconnect();
        }
        self.backend.refresh_and_remove_absent();
        // Publish this attempt's missing readings. Reconnect on the next sample
        // so a dead service handle cannot prevent rediscovery of its replacement.
        self.reconnect = self.backend.needs_reconnect();
        &self.backend
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Default)]
    struct Backend {
        refreshes: usize,
        values: Vec<Option<f32>>,
        next_values: Vec<Option<f32>>,
    }

    impl TemperatureBackend for Backend {
        fn reconnect(&mut self) {
            self.refreshes = 0;
            self.values.clear();
        }

        fn refresh_and_remove_absent(&mut self) {
            self.refreshes += 1;
            self.values = std::mem::take(&mut self.next_values);
        }

        fn needs_reconnect(&self) -> bool {
            self.values.is_empty() || self.values.iter().any(Option::is_none)
        }
    }

    #[test]
    fn healthy_inventory_refreshes_values_and_discovers_every_sample() {
        let mut inventory = TemperatureInventory::<Backend>::default();
        inventory.backend.next_values = vec![Some(30.)];
        assert_eq!(inventory.refresh().values, [Some(30.)]);
        inventory.backend.next_values = vec![Some(40.), Some(50.)];
        assert_eq!(inventory.refresh().values, [Some(40.), Some(50.)]);
        assert_eq!(inventory.backend.refreshes, 2);
        inventory.backend.next_values = vec![Some(45.)];
        assert_eq!(inventory.refresh().values, [Some(45.)]);
        assert!(!inventory.reconnect);
    }

    #[test]
    fn failed_read_is_not_cached_and_reconnect_replaces_dead_handles() {
        let mut inventory = TemperatureInventory::<Backend>::default();
        inventory.backend.next_values = vec![Some(30.)];
        inventory.refresh();
        inventory.backend.next_values = vec![None];
        assert_eq!(inventory.refresh().values, [None]);
        assert!(inventory.reconnect);
        inventory.backend.next_values = vec![Some(55.)];
        assert_eq!(inventory.refresh().values, [Some(55.)]);
        assert_eq!(inventory.backend.refreshes, 1);
        assert!(!inventory.reconnect);
    }

    #[test]
    fn empty_discovery_retries_without_retaining_historical_inventory() {
        let mut inventory = TemperatureInventory::<Backend>::default();
        for _ in 0..100 {
            assert!(inventory.refresh().values.is_empty());
            assert_eq!(inventory.backend.refreshes, 1);
            assert!(inventory.reconnect);
        }
    }
}
