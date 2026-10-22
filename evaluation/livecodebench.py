"""Prepare a typed call-based subset and use the unmodified official LCB grader."""

import ast
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import pickle
import random
import sys
import zlib


ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache/lcb-data"
TASKS = ROOT / "livecodebench/tasks.json"
DATASET_REVISION = "175d0ac20500fd7aa0813f7a2e6ae7ecad3c76c9"
HARNESS_REVISION = "28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24"
SEED = 20261018
TIMEOUT = 6
FILES = [f"release_v6/test-{i:05d}-of-00009.parquet" for i in range(9)]
FIELDS = ["question_title", "question_content", "platform", "question_id", "contest_id",
          "contest_date", "starter_code", "difficulty", "metadata"]


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def parquet_source(filename):
    sys.path.insert(0, str(ROOT / ".cache/lcb-deps"))
    import fsspec
    url = ("https://huggingface.co/datasets/livecodebench/code_generation_lite/resolve/"
           + DATASET_REVISION + "/" + filename)
    return fsspec.open(url, "rb", block_size=1048576, cache_type="bytes")


def normalized_type(node):
    if isinstance(node, ast.Constant):
        if node.value is None:
            return node
        if isinstance(node.value, str):
            return normalized_type(ast.parse(node.value, mode="eval").body)
    if isinstance(node, ast.Name) and node.id in {"int", "float", "bool", "str", "object"}:
        return node
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return ast.BinOp(normalized_type(node.left), ast.BitOr(), normalized_type(node.right))
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        name = {"List": "list", "Tuple": "tuple", "Dict": "dict", "Optional": "optional"}.get(node.value.id, node.value.id)
        if name == "optional":
            return ast.BinOp(normalized_type(node.slice), ast.BitOr(), ast.Constant(None))
        if name == "list":
            return ast.Subscript(ast.Name("list", ast.Load()), normalized_type(node.slice), ast.Load())
        if name in {"dict", "tuple"} and isinstance(node.slice, ast.Tuple):
            items = [normalized_type(item) for item in node.slice.elts]
            if name == "dict" and (len(items) != 2 or ast.unparse(items[0]) != "str"):
                raise ValueError("dictionary keys must be str")
            return ast.Subscript(ast.Name(name, ast.Load()), ast.Tuple(items, ast.Load()), ast.Load())
    raise ValueError("unsupported or missing interface annotation")


def interface(row):
    if row["platform"] != "leetcode" or not row["starter_code"].strip():
        raise ValueError("not a call-based LeetCode interface")
    source = row["starter_code"].rstrip()
    last = source.splitlines()[-1]
    if last.rstrip().endswith(":"):
        source += "\n" + " " * (len(last) - len(last.lstrip()) + 4) + "pass\n"
    module = ast.parse(source)
    classes = [n for n in module.body if isinstance(n, ast.ClassDef)]
    if len(classes) != 1 or classes[0].name != "Solution":
        raise ValueError("expected one Solution class")
    methods = [n for n in classes[0].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(methods) != 1 or not isinstance(methods[0], ast.FunctionDef):
        raise ValueError("expected one ordinary method")
    function = copy.deepcopy(methods[0])
    if function.decorator_list or not function.args.args or function.args.args[0].arg != "self":
        raise ValueError("unsupported method binding")
    args = function.args
    if args.defaults or args.kw_defaults or args.vararg or args.kwarg or args.posonlyargs or args.kwonlyargs:
        raise ValueError("unsupported parameter convention")
    args.args = args.args[1:]
    for arg in args.args:
        arg.annotation = normalized_type(arg.annotation)
    function.returns = normalized_type(function.returns)
    function.body = [ast.Pass()]
    if json.loads(row["metadata"]).get("func_name") != function.name:
        raise ValueError("metadata and starter method disagree")
    signature = ast.unparse(ast.fix_missing_locations(function)).splitlines()[0]
    return function.name, [arg.arg for arg in args.args], signature


class PrimitiveUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError("official test payload must contain primitive data only")


def decode_private(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raw = zlib.decompress(base64.b64decode(text))
        return json.loads(PrimitiveUnpickler(io.BytesIO(raw)).load())


def case_path(task_id):
    return CACHE / "cases" / (hashlib.sha256(task_id.encode()).hexdigest()[:24] + ".json")


def ensure_cases(tasks):
    import pyarrow.parquet as pq
    missing = set()
    for task_id, task in tasks.items():
        path = case_path(task_id)
        if not path.exists():
            missing.add(task_id)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != task["tests_sha256"]:
            raise RuntimeError(f"cached official tests changed: {task_id}")
    if not missing:
        return
    for filename in FILES:
        with parquet_source(filename) as source:
            parquet = pq.ParquetFile(source)
            for group_index in range(parquet.num_row_groups):
                rows = parquet.read_row_group(group_index, columns=[
                    "platform", "question_id", "starter_code", "metadata"]).to_pylist()
                selected = [(i, row, "LiveCodeBench/" + row["platform"] + "/" + row["question_id"])
                            for i, row in enumerate(rows)
                            if "LiveCodeBench/" + row["platform"] + "/" + row["question_id"] in missing]
                if not selected:
                    continue
                print(f"Downloading official tests for {len(selected)} frozen tasks from {filename}", flush=True)
                table = parquet.read_row_group(group_index, columns=["public_test_cases", "private_test_cases"])
                for index, row, task_id in selected:
                    task = tasks[task_id]
                    if interface(row) != (task["name"], task["parameters"], task["signature"]):
                        raise RuntimeError(f"official test interface changed: {task_id}")
                    public = json.loads(table["public_test_cases"][index].as_py())
                    private = decode_private(table["private_test_cases"][index].as_py())
                    tests = public + private
                    if not tests or not all(test["testtype"] == "functional" for test in tests):
                        raise RuntimeError(f"official tests are not functional: {task_id}")
                    fixture = {"sample": {"input_output": json.dumps({
                        "inputs": [test["input"] for test in tests],
                        "outputs": [test["output"] for test in tests], "fn_name": task["name"]})},
                        "public_count": len(public), "private_count": len(private)}
                    raw = (json.dumps(fixture, ensure_ascii=False, indent=2) + "\n").encode()
                    if (len(tests) != task["test_count"]
                            or hashlib.sha256(raw).hexdigest() != task["tests_sha256"]):
                        raise RuntimeError(f"downloaded official tests changed: {task_id}")
                    dump(case_path(task_id), fixture)
                    missing.remove(task_id)
                del table
        if not missing:
            return
    raise RuntimeError("official tests not found for frozen tasks: " + ", ".join(sorted(missing)))


def prepare():
    if TASKS.exists():
        frozen = json.loads(TASKS.read_text())
        if (frozen["manifest"]["dataset_revision"] != DATASET_REVISION
                or frozen["manifest"]["harness_revision"] != HARNESS_REVISION):
            raise RuntimeError("frozen LiveCodeBench revisions changed")
        ensure_cases(frozen["tasks"])
        print(f"Using the frozen selection: {TASKS}")
        return
    sys.path.insert(0, str(ROOT / ".cache/lcb-deps"))
    import pyarrow.parquet as pq
    candidates = []
    audit = []
    for file_index, filename in enumerate(FILES):
        cache = CACHE / f"metadata-{file_index}.json"
        if not cache.exists():
            with parquet_source(filename) as source:
                rows = pq.ParquetFile(source).read(columns=FIELDS).to_pylist()
            dump(cache, rows)
        rows = json.loads(cache.read_text())
        for row_index, row in enumerate(rows):
            if row["difficulty"] not in {"medium", "hard"}:
                continue
            try:
                name, params, signature = interface(row)
            except (ValueError, SyntaxError, TypeError) as error:
                audit.append({"id": row["question_id"], "eligible": False, "reason": str(error)})
                continue
            candidates.append({**row, "file_index": file_index, "row_index": row_index,
                               "name": name, "parameters": params, "signature": signature})
            audit.append({"id": row["question_id"], "eligible": True})
        print(f"Metadata {file_index + 1}/9 loaded", flush=True)
    rng = random.Random(SEED)
    pools = {level: [r for r in candidates if r["difficulty"] == level] for level in ("medium", "hard")}
    if any(len(pool) < 20 for pool in pools.values()):
        raise RuntimeError(f"insufficient compatible tasks: { {k: len(v) for k, v in pools.items()} }")
    chosen = rng.sample(pools["medium"], 20) + rng.sample(pools["hard"], 20)
    rng.shuffle(chosen)
    tasks = {}
    for row in chosen:
        task_id = "LiveCodeBench/leetcode/" + row["question_id"]
        tasks[task_id] = {key: row[key] for key in ("name", "signature", "parameters", "difficulty", "contest_date")}
        tasks[task_id].update({"source_title": row["question_title"], "platform": row["platform"],
                              "original_starter_code": row["starter_code"],
                              "question": "This is a function-interface adaptation of LiveCodeBench. Implement the required top-level function, not a Solution class. A fixed external adapter supplies the benchmark's Solution method; do not write the adapter. The problem and tests are unchanged.\n\n" + row["question_content"]})
        existing = case_path(task_id)
        if existing.exists():
            fixture = json.loads(existing.read_text())
            if json.loads(fixture["sample"]["input_output"])["fn_name"] != row["name"]:
                raise RuntimeError("cached test interface mismatch")
            tasks[task_id]["tests_sha256"] = hashlib.sha256(existing.read_bytes()).hexdigest()
            tasks[task_id]["test_count"] = fixture["public_count"] + fixture["private_count"]
    for file_index, filename in enumerate(FILES):
        selected = [r for r in chosen if r["file_index"] == file_index
                    and not case_path("LiveCodeBench/leetcode/" + r["question_id"]).exists()]
        if not selected:
            continue
        with parquet_source(filename) as source:
            parquet = pq.ParquetFile(source)
            offset = 0
            for group_index in range(parquet.num_row_groups):
                count = parquet.metadata.row_group(group_index).num_rows
                selected_group = [r for r in selected if offset <= r["row_index"] < offset + count]
                if selected_group:
                    table = parquet.read_row_group(group_index, columns=["public_test_cases", "private_test_cases"])
                    for row in selected_group:
                        task_id = "LiveCodeBench/leetcode/" + row["question_id"]
                        local_index = row["row_index"] - offset
                        public_raw = table["public_test_cases"][local_index].as_py()
                        private_raw = table["private_test_cases"][local_index].as_py()
                        public = json.loads(public_raw)
                        private = decode_private(private_raw)
                        tests = public + private
                        if not tests or not all(t["testtype"] == "functional" for t in tests):
                            raise RuntimeError(f"selected task has incompatible tests: {task_id}")
                        fixture = {"input_output": json.dumps({"inputs": [t["input"] for t in tests],
                                   "outputs": [t["output"] for t in tests], "fn_name": row["name"]})}
                        dump(case_path(task_id), {"sample": fixture, "public_count": len(public), "private_count": len(private)})
                        tasks[task_id]["tests_sha256"] = hashlib.sha256(case_path(task_id).read_bytes()).hexdigest()
                        tasks[task_id]["test_count"] = len(tests)
                    del table
                offset += count
        print(f"Official tests from file {file_index + 1}/9 saved", flush=True)
    manifest = {"benchmark": "LiveCodeBench", "release": "release_v6", "dataset_revision": DATASET_REVISION,
                "harness_revision": HARNESS_REVISION, "seed": SEED, "selected_medium": 20, "selected_hard": 20,
                "eligible_counts": {k: len(v) for k, v in pools.items()},
                "scope": "typed interface-compatible call-based LeetCode subset, not all LiveCodeBench",
                "adapter": "same external Solution wrapper for all models and both conditions; checker evaluates generated core only",
                "official_timeout_per_test_seconds": TIMEOUT,
                "contamination_note": "No contamination-free claim; record task dates and model training cutoffs separately."}
    dump(CACHE / "selection-audit.json", audit)
    dump(TASKS, {"benchmark": "LiveCodeBench", "manifest": manifest, "tasks": tasks})
    print(f"Frozen 20 medium + 20 hard tasks: {TASKS}", flush=True)


if __name__ == "__main__":
    prepare()
