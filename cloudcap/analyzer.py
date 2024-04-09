import enum
from typing import Any
from cloudcap.plugins import Plugin, builtin_plugins
from cloudcap.metrics import Metric

from z3 import *  # type: ignore
from cloudcap.aws import AWS, Arn, Resource

Constraint = Any
Variable = Any
NodeVariableIndex = tuple[Resource, str]
EdgeVariableIndex = tuple[Resource, Resource, str]


class AnalyzerResult(enum.Enum):
    PASS = 1
    REJECT = 2
    UNKNOWN = 3


class Analyzer:
    aws: AWS
    plugins: list[Plugin]
    solver: Any
    node_variables: dict[NodeVariableIndex, Variable]
    edge_variables: dict[EdgeVariableIndex, Variable]

    def __init__(self, aws: AWS) -> None:
        # initialize with builtin plugins
        self.aws = aws
        self.plugins = [p(self) for p in builtin_plugins.plugins]
        self.solver = z3.Solver()
        self.node_variables = {}
        self.edge_variables = {}

    def add_plugin(self, plugin: type[Plugin]) -> None:
        self.plugins.append(plugin(self))

    def constrain(self):
        for plugin in self.plugins:
            plugin.constrain(self.aws)

    def solve(self) -> AnalyzerResult:
        return self.solver.solve()

    def __getitem__(self, key: NodeVariableIndex | EdgeVariableIndex) -> Variable:
        if not isinstance(key, tuple) and (len(key) == 2 or len(key == 3)):  # type: ignore
            raise KeyError(
                f"Analyzer.__getitem__ expected a tuple of length 2 or 3, but got a {type(key)}. Got: {key}"
            )

        if len(key) == 2:
            # node variable
            resource = key[0]
            metric = key[1]
            assert isinstance(resource, Resource) and isinstance(metric, Metric)
            if not (resource, metric) in self.node_variables:
                v = Int(format_arn_for_z3(resource.arn))  # type: ignore
                self.node_variables[(resource, metric)] = v
            return self.node_variables[(resource, metric)]
        elif len(key) == 3:
            # edge variable
            resource1 = key[0]
            resource2 = key[1]
            metric = key[2]
            assert (
                isinstance(resource1, Resource)
                and isinstance(resource2, Resource)
                and isinstance(metric, Metric)
            )
            if not (resource1, resource2, metric) in self.edge_variables:
                v = Int(format_arn_for_z3(resource.arn))  # type: ignore
                self.edge_variables[(resource1, resource2, metric)] = v
            return self.edge_variables[(resource1, resource2, metric)]
        else:
            raise KeyError(
                f"Analyzer.__getitem__ expected 2 or 3 keys, but got {len(key)} items"
            )

    def add(self, *args: list[Constraint]) -> None:
        self.solver.add(*args)

    def sexpr(self) -> Any:
        return self.solver.sexpr()


def format_arn_for_z3(arn: Arn) -> str:
    return arn.replace(":", "_")
