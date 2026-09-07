"""Native navigation for the fixed-screen product, sharing bounded transport."""

from native_driver import Native, Atspi
from host_accuracy import require
from tabbed_contract import SCREENS, clipped_visible


class TabbedNative(Native):
    def visible(self, node):
        geometry = self.window().get_geometry()
        return clipped_visible(
            self.bounds(node), [0, 0, geometry.width, geometry.height], self.ancestors(node)
        )

    def panel(self, mid):
        require(mid in SCREENS, "unknown fixed screen")
        return self.find(aid="screen:" + mid)

    def selected_screen(self):
        selected = [
            node.get_accessible_id().removeprefix("screen-tab:")
            for node in self.walk(self.find(aid="screen-tabs"), strict=True)
            if (node.get_accessible_id() or "").startswith("screen-tab:")
            and node.get_state_set().contains(Atspi.StateType.SELECTED)
        ]
        # Accessibility selection can briefly transition between two tree updates.
        # Callers wait for exactly one selected tab and reject a lasting mismatch.
        return selected[0] if len(selected) == 1 else None

    def select_screen(self, screen):
        require(screen in SCREENS, "unknown fixed screen")
        tab = self.find(aid="screen-tab:" + screen)
        require(self.visible(tab), "tab is clipped")
        self.click(tab)
        self.wait(lambda: self.selected_screen() == screen, message="selected " + screen)
        self.panel(screen)
        self.wait(lambda: self.state()["screens"]["active"] == screen, 10, "saved " + screen)

    def save_state(self):
        active = self.selected_screen()
        return self.wait(
            lambda: self.state() if self.state()["screens"]["active"] == active else None,
            10, "autosaved active screen",
        )
