from __future__ import annotations
from collections import defaultdict
import enum
from typing import Any
from cloudcap.plugins import Plugin, builtin_plugins
from cloudcap.metrics import NREQUESTS, Metric
from cloudcap import utils

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

    @staticmethod
    def from_z3_check_result(z3result: Any) -> AnalyzerResult:
        match z3result:
            case z3.sat:
                return AnalyzerResult.PASS
            case z3.unsat:
                return AnalyzerResult.REJECT
            case z3.unknown:
                return AnalyzerResult.UNKNOWN
            case _:
                return AnalyzerResult.UNKNOWN


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

    def constrain(self) -> None:
        # call all plugins
        for plugin in self.plugins:
            plugin.constrain()

        # generate incoming constraints
        incomings_map: defaultdict[tuple[Resource, Metric], list[Variable]] = (
            defaultdict(list)
        )
        for (_, resource2, metric), var in self.edge_variables.items():
            incomings_map[(resource2, metric)].append(var)

        for (resource, metric), incomings in incomings_map.items():
            self.add(self[resource, metric] == sum(incomings[1:], incomings[0]))

        # generate basic constraints
        # TODO: only doing NREQUESTS >= 0 for now
        self.add(
            *[
                var >= 0
                for (_, metric), var in self.node_variables.items()
                if metric == NREQUESTS
            ]
        )
        self.add(
            *[
                var >= 0
                for (_, _, metric), var in self.edge_variables.items()
                if metric == NREQUESTS
            ]
        )

    def solve(self) -> AnalyzerResult:
        return AnalyzerResult.from_z3_check_result(self.solver.check())

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
            if (resource, metric) not in self.node_variables:
                v_name = f"{resource.arn}.{metric}"
                v = Int(v_name)  # type: ignore
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
            if (resource1, resource2, metric) not in self.edge_variables:
                v_name = f"{resource1.arn}.{resource2.arn}.{metric}"
                v = Int(v_name)  # type: ignore
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
