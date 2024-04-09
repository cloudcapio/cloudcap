from __future__ import annotations
import abc
from typing import Any
from cloudcap.aws import AWS
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cloudcap.analyzer import Analyzer, Constraint, Variable

# import z3


class Plugin(abc.ABC):
    def __init__(self, analyzer: Analyzer) -> None:
        super().__init__()
        self.analyzer = analyzer

    def __getitem__(self, key: Any) -> Variable:
        return self.analyzer[key]

    def add(self, *args: list[Constraint]) -> None:
        self.analyzer.add(*args)

    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError("Plugins need to have a name() method")

    @abc.abstractmethod
    def constrain(self, aws: AWS) -> None:
        raise NotImplementedError("Plugins need to have a constrain() method")
