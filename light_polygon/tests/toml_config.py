from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomli_w
import tomllib

from light_polygon.problem import layout


@dataclass
class ManualTest:
    index: int
    description: str = ""
    is_sample: bool = False
    input: str = ""
    answer: str = ""


@dataclass
class GeneratorInvocation:
    args: list[str] = field(default_factory=list)
    answer_by: str = ""
    count: int = 1
    description: str = ""


@dataclass
class GeneratorConfig:
    name: str
    source: str
    testset: str = "tests"
    invocations: list[GeneratorInvocation] = field(default_factory=list)


@dataclass
class TestsToml:
    __test__ = False
    slug: str
    tests: list[ManualTest] = field(default_factory=list)
    generators: list[GeneratorConfig] = field(default_factory=list)


def read_tests_toml(slug: str) -> TestsToml:
    path = layout.tests_toml_path(slug)
    if not path.exists():
        return TestsToml(slug=slug)

    with open(path, "rb") as f:
        data = tomllib.load(f)

    result = TestsToml(slug=slug)

    for t in data.get("tests", []):
        result.tests.append(ManualTest(
            index=t.get("index", 0),
            description=t.get("description", ""),
            is_sample=t.get("is_sample", False),
            input=t.get("input", ""),
            answer=t.get("answer", ""),
        ))

    generators_data = data.get("generators", {})
    for gen_name, gen_data in generators_data.items():
        invocations = []
        for inv in gen_data.get("invocations", []):
            invocations.append(GeneratorInvocation(
                args=inv.get("args", []),
                answer_by=inv.get("answer_by", ""),
                count=inv.get("count", 1),
                description=inv.get("description", ""),
            ))
        result.generators.append(GeneratorConfig(
            name=gen_name,
            source=gen_data.get("source", ""),
            testset=gen_data.get("testset", "tests"),
            invocations=invocations,
        ))

    return result


def write_tests_toml(slug: str, config: TestsToml) -> None:
    data: dict = {}

    if config.tests:
        data["tests"] = []
        for t in config.tests:
            entry: dict = {"index": t.index}
            if t.description:
                entry["description"] = t.description
            if t.is_sample:
                entry["is_sample"] = True
            if t.input:
                entry["input"] = t.input
            if t.answer:
                entry["answer"] = t.answer
            data["tests"].append(entry)

    if config.generators:
        data["generators"] = {}
        for g in config.generators:
            gen_entry: dict = {"source": g.source}
            if g.testset != "tests":
                gen_entry["testset"] = g.testset
            if g.invocations:
                gen_entry["invocations"] = []
                for inv in g.invocations:
                    inv_entry: dict = {}
                    if inv.args:
                        inv_entry["args"] = inv.args
                    if inv.answer_by:
                        inv_entry["answer_by"] = inv.answer_by
                    if inv.count != 1:
                        inv_entry["count"] = inv.count
                    if inv.description:
                        inv_entry["description"] = inv.description
                    gen_entry["invocations"].append(inv_entry)
            data["generators"][g.name] = gen_entry

    path = layout.tests_toml_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def generate_template_toml(slug: str) -> str:
    return f"""# Test generation config for '{slug}'
# Edit this file to define how tests are created.

# ─── Hand-written tests ──────────────────────────────────────────────
# Each [[tests]] entry defines a manual test with inline data.

#[[tests]]
#index = 1
#description = "样例"
#is_sample = true
#input = \"\"\"
#3
#1 2 3
#\"\"\"
#answer = \"\"\"
#6
#\"\"\"


# ─── Generators ───────────────────────────────────────────────────────
# Each [generators.<name>] defines a C++ generator using testlib.h.
# Generators must be in the problem's 'generators/' directory.
#
# Each invocation runs the generator with given args.
# - args: CLI arguments passed to the generator
# - answer_by: solution name used to produce the answer file (optional)
# - count: number of tests with different seeds (default 1)
#
# The generator must call registerGen(argc, argv, 1) for seed support.

# [generators.gen_example]
# source = "gen_example.cpp"
# testset = "tests"
#
# [[generators.gen_example.invocations]]
# args = ["10", "100"]
# answer_by = "main.cpp"
# count = 5
"""
