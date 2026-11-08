#!/usr/bin/env python3
"""Small regression tests for the benchmark answer parser."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from answer_json import parse_answer_json


class AnswerJsonTest(unittest.TestCase):
    def test_strict(self):
        obj, repaired = parse_answer_json(
            '{"task_id":"x","found":true,"answer":{"drivers":[]}}')
        self.assertEqual(obj["task_id"], "x")
        self.assertFalse(repaired)

    def test_single_quote_repair(self):
        obj, repaired = parse_answer_json(
            "{\"task_id\":'x',\"found\":true,\"answer\":{\"drivers\":[]}}")
        self.assertEqual(obj["task_id"], "x")
        self.assertEqual(obj["answer"]["drivers"], [])
        self.assertTrue(repaired)

    def test_nested_answer_is_not_mistaken_for_top_level(self):
        obj, repaired = parse_answer_json(
            'prose {"task_id":"x","found":true,"answer":{"drivers":[]}} tail')
        self.assertEqual(obj["task_id"], "x")
        self.assertFalse(repaired)

    def test_no_json(self):
        obj, repaired = parse_answer_json("not json")
        self.assertIsNone(obj)
        self.assertFalse(repaired)


if __name__ == "__main__":
    unittest.main()
