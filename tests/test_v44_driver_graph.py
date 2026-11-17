"""V44 three-degree BTC/AUD driver graph integrity tests."""
import json
import unittest
from pathlib import Path


class V44DriverGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = json.loads(Path(
            "research/v44_btc_aud_driver_graph.json").read_text())

    def test_graph_is_explicitly_hypothetical_and_has_valid_edges(self):
        graph = self.graph
        self.assertEqual(graph["schema"], "v44_btc_aud_driver_graph_1")
        self.assertEqual(graph["status"], "HYPOTHESIS_GRAPH_NOT_CAUSAL_EVIDENCE")
        ids = {node["id"] for node in graph["nodes"]}
        self.assertEqual(len(ids), len(graph["nodes"]))
        for edge in graph["edges"]:
            self.assertIn(edge["from"], ids)
            self.assertIn(edge["to"], ids)
            self.assertIn(edge["degree"], (0, 1, 2, 3))
            self.assertTrue(edge["channel"])
            self.assertTrue(edge["sign"])
            self.assertTrue(edge["lag"])
            self.assertEqual(edge["evidence_status"], "hypothesis_only")

    def test_all_three_proximity_degrees_have_source_provenance(self):
        nodes = self.graph["nodes"]
        for degree in (1, 2, 3):
            selected = [node for node in nodes if node["degree"] == degree]
            self.assertGreaterEqual(len(selected), 10 if degree == 3 else 8)
            self.assertTrue(all(node["preferred_sources"] for node in selected))

    def test_cross_rate_denominator_sign_is_explicit(self):
        text = self.graph["sign_convention"]["denominator_identity"]
        self.assertIn("AUD/USD up", text)
        self.assertIn("BTC/AUD down", text)
        edges = [edge for edge in self.graph["edges"]
                 if edge["from"] == "aud_usd" and edge["to"] == "btc_aud"]
        self.assertEqual(len(edges), 1)
        self.assertIn("negative", edges[0]["sign"])

    def test_required_research_controls_are_prespecified(self):
        required = self.graph["method"]["required_tests"]
        for term in ("point-in-time", "matched-time", "walk-forward",
                     "randomized", "multiple-testing", "80bps",
                     "A$100"):
            self.assertTrue(any(term.lower() in item.lower()
                                for item in required), term)


if __name__ == "__main__":
    unittest.main()
