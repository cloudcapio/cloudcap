import enum
from typing import Any
from cloudcap.plugins import Plugin

import z3  # type: ignore
from cloudcap.aws import AWS


class AnalyzerResult(enum.Enum):
    PASS = 1
    REJECT = 2
    UNKNOWN = 3


class Analyzer:
    plugins: list[Plugin]
    solver: Any

    def __init__(self) -> None:
        self.plugins = []
        self.solver = z3.Solver()

    def add_plugin(self, plugin: Plugin) -> None:
        self.plugins.append(plugin)

    def analyze(self, aws: AWS) -> AnalyzerResult:
        return AnalyzerResult.PASS
