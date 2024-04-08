import abc
from typing import Any
from cloudcap.aws import AWS

# import z3


class Plugin(abc.ABC):
    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    def constrain(self, aws: AWS) -> list[Any]:
        return []
