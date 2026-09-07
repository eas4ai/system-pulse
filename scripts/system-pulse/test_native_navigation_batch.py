"""Distant traversal retains exact acknowledgements within the original deadline."""

import copy
import unittest

import native_pending
import test_native_navigation as navigation

aid = navigation.aid


class NavigationBatchTests(unittest.TestCase):
    def fixture(self, target):
        f = navigation.NavigationTests(methodName="runTest")
        f.setUp()
        f.ids = [aid(pid) for pid in range(400)]
        f.nodes = {identity: f.row(identity) for identity in f.ids}
        f.target = aid(target)
        f.ack_delay = 3
        return f

    def test_distant_targets_finish_with_delayed_exact_acknowledgements(self):
        for target in (180, 219):
            with self.subTest(target=target):
                f = self.fixture(target)
                result = f.navigate()
                self.assertEqual(result[0], f.target)
                self.assertLess(f.clock.now, 180)
                batches = [
                    event[1] for event in f.events if event[0] == "navigation-batch"
                ]
                self.assertTrue(any(batch["count"] == 8 for batch in batches))
                self.assertTrue(all(1 <= batch["count"] <= 8 for batch in batches))
                self.assertTrue(
                    all(
                        batch["count"] <= 2
                        for batch in batches
                        if batch["distance"] <= 32
                    )
                )
                for index, event in enumerate(f.events):
                    if event[0] != "navigation-batch":
                        continue
                    expected = event[1]["expected"]
                    following = f.events[index + 1 :]
                    next_batch = next(
                        (
                            i
                            for i, item in enumerate(following)
                            if item[0] == "navigation-batch"
                        ),
                        len(following),
                    )
                    self.assertTrue(
                        any(
                            item[0] == "ack"
                            and item[1]["condition"] == "selected " + expected
                            for item in following[:next_batch]
                        )
                    )

    def test_wrong_distant_endpoint_cannot_authorize_the_next_batch(self):
        f = self.fixture(180)
        key = f.native.key
        arrows = 0

        def drop_one(value, **kwargs):
            nonlocal arrows
            if value == "Down":
                arrows += 1
                if arrows == 8:
                    return
            key(value, **kwargs)

        f.native.key = drop_one
        with self.assertRaises(TimeoutError):
            f.navigate()
        self.assertEqual(arrows, 8)
        self.assertEqual(len([e for e in f.events if e[0] == "navigation-batch"]), 1)
        self.assertLess(f.clock.now, 12)

    def proof(self, keys):
        ids = [aid(pid) for pid in range(1, 65)]
        publication = {
            "sequence": 1,
            "application_pid": 500,
            "render_revision": 1,
            "accepted_unix_ns": 1,
        }
        acknowledgement = {"identity": ids[0], "index": 0, "publication": publication}
        pending = {
            "issued_selection": ids[0],
            "expected": ids[len(keys)],
            "target": ids[-1],
            "endpoint_index": len(keys),
            "publication": publication,
            "keys": keys,
            "batch_deadline": 8,
            "deadline": 180,
        }
        proof = native_pending.prepare_prior_acknowledgement(
            acknowledgement, pending, ids
        )
        return pending, proof

    def test_eight_key_prefix_binds_count_and_expires_without_acknowledging(self):
        pending, proof = self.proof(["Down"] * 8)
        self.assertIsNotNone(proof)
        pending.update(dispatch_started=1, dispatch_completed=2)
        proof.update(dispatch_started=1, dispatch_completed=2)
        pending["prior_acknowledgement"] = proof
        prefix = native_pending.PriorSelectionPrefix(pending)
        self.assertTrue(prefix.selection(pending["issued_selection"]))
        self.assertFalse(prefix.selection(pending["expected"]))
        self.assertFalse(prefix.selection(pending["issued_selection"]))
        malformed = copy.deepcopy(pending)
        malformed["keys"] = ["Down"] * 9
        malformed["prior_acknowledgement"]["keys"] = ["Down"] * 9
        malformed["endpoint_index"] = 9
        malformed["prior_acknowledgement"]["endpoint_index"] = 9
        with self.assertRaises(AssertionError):
            native_pending.PriorSelectionPrefix(malformed)

    def test_mixed_empty_and_oversized_batches_cannot_capture_a_prefix(self):
        for keys in ([], ["Down", "Up"], ["Down"] * 9):
            with self.subTest(keys=keys):
                self.assertIsNone(self.proof(keys)[1])


if __name__ == "__main__":
    unittest.main()
