import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

import livecodebench as lcb


class FrozenCaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.files = ["first.parquet", "second.parquet"]
        self.tasks = {}
        self.fixtures = {}
        for index, filename in enumerate(self.files):
            question_id = str(index + 100)
            task_id = "LiveCodeBench/leetcode/" + question_id
            name = "solve_" + question_id
            public = [{"input": "[1, 2]", "output": "3", "testtype": "functional"}]
            private = [{"input": "[4]", "output": "4", "testtype": "functional"}]
            row = {"platform": "leetcode", "question_id": question_id,
                   "starter_code": f"class Solution:\n    def {name}(self, nums: List[int]) -> int:\n        pass\n",
                   "metadata": json.dumps({"func_name": name}),
                   "public_test_cases": json.dumps(public), "private_test_cases": json.dumps(private)}
            pq.write_table(pa.Table.from_pylist([row]), self.root / filename)
            tests = public + private
            fixture = {"sample": {"input_output": json.dumps({"inputs": [t["input"] for t in tests],
                       "outputs": [t["output"] for t in tests], "fn_name": name})},
                       "public_count": 1, "private_count": 1}
            raw = (json.dumps(fixture, ensure_ascii=False, indent=2) + "\n").encode()
            self.fixtures[task_id] = fixture
            self.tasks[task_id] = {"name": name, "parameters": ["nums"],
                                  "signature": f"def {name}(nums: list[int]) -> int:",
                                  "test_count": 2, "tests_sha256": hashlib.sha256(raw).hexdigest()}
        self.selection = self.root / "tasks.json"
        self.manifest = {"dataset_revision": lcb.DATASET_REVISION, "harness_revision": lcb.HARNESS_REVISION}
        self.save_selection()
        for name, value in [("CACHE", self.root / "cases-cache"), ("TASKS", self.selection), ("FILES", self.files)]:
            context = patch.object(lcb, name, value)
            context.start()
            self.addCleanup(context.stop)
        source = patch.object(lcb, "parquet_source", side_effect=lambda name: (self.root / name).open("rb"))
        self.source = source.start()
        self.addCleanup(source.stop)

    def save_selection(self):
        lcb.dump(self.selection, {"manifest": self.manifest, "tasks": self.tasks})

    def test_missing_cases_download_without_changing_selection(self):
        task_id = next(iter(self.tasks))
        lcb.dump(lcb.case_path(task_id), self.fixtures[task_id])
        before = self.selection.read_bytes()
        lcb.prepare()
        self.assertEqual(self.selection.read_bytes(), before)
        for task_id, task in self.tasks.items():
            path = lcb.case_path(task_id)
            self.assertEqual(json.loads(path.read_text()), self.fixtures[task_id])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), task["tests_sha256"])
        self.assertEqual(self.source.call_count, 2)
        self.source.reset_mock()
        lcb.prepare()
        self.source.assert_not_called()

    def test_changed_cached_tests_fail_before_download(self):
        task_id = next(iter(self.tasks))
        lcb.dump(lcb.case_path(task_id), {"changed": True})
        with self.assertRaisesRegex(RuntimeError, "cached official tests changed"):
            lcb.prepare()
        self.source.assert_not_called()

    def test_downloaded_cases_require_the_frozen_checksum(self):
        task_id = next(iter(self.tasks))
        self.tasks[task_id]["tests_sha256"] = "0" * 64
        self.save_selection()
        before = self.selection.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "downloaded official tests changed"):
            lcb.prepare()
        self.assertFalse(lcb.case_path(task_id).exists())
        self.assertEqual(self.selection.read_bytes(), before)

    def test_downloaded_cases_require_the_frozen_interface(self):
        task_id = next(iter(self.tasks))
        self.tasks[task_id]["name"] = "different"
        self.save_selection()
        with self.assertRaisesRegex(RuntimeError, "official test interface changed"):
            lcb.prepare()
        self.assertFalse(lcb.case_path(task_id).exists())

    def test_missing_task_fails_without_resampling(self):
        self.tasks = {"LiveCodeBench/leetcode/absent": next(iter(self.tasks.values()))}
        self.save_selection()
        before = self.selection.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "official tests not found for frozen tasks"):
            lcb.prepare()
        self.assertEqual(self.selection.read_bytes(), before)

    def test_changed_revisions_fail_before_download(self):
        self.manifest["dataset_revision"] = "different"
        self.save_selection()
        with self.assertRaisesRegex(RuntimeError, "frozen LiveCodeBench revisions changed"):
            lcb.prepare()
        self.source.assert_not_called()


if __name__ == "__main__":
    unittest.main()
