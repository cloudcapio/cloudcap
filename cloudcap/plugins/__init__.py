from __future__ import annotations
import abc
from cloudcap.aws import AWS
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cloudcap.analyzer import (
        Analyzer,
        Constraint,
        Variable,
        EdgeVariableIndex,
        NodeVariableIndex,
    )

# import z3


class Plugin(abc.ABC):
    def __init__(self, analyzer: Analyzer) -> None:
        super().__init__()
        self.analyzer = analyzer

    def __getitem__(self, key: NodeVariableIndex | EdgeVariableIndex) -> Variable:
        return self.analyzer[key]

    def add(self, *args: list[Constraint]) -> None:
        self.analyzer.add(*args)

    @property
    def aws(self) -> AWS:
        return self.analyzer.aws

    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError("Plugins need to have a name() method")

    @abc.abstractmethod
    def constrain(self) -> None:
        raise NotImplementedError("Plugins need to have a constrain() method")
