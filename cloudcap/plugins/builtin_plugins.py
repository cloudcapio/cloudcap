from cloudcap.metrics import NREQUESTS
from cloudcap.plugins import Plugin
from cloudcap.aws import AWS


class BasicPlugin(Plugin):
    def name(self) -> str:
        return "builtin_basic_plugin"

    def constrain(self, aws: AWS) -> None:
        for resource in aws.resources:
            self.add(self[resource, NREQUESTS] >= 0)


class AWSSQSQueuePlugin(Plugin):
    def name(self) -> str:
        return "builtin_aws_sqs_queue_plugin"

    def constrain(self, aws: AWS) -> None:
        raise NotImplementedError


plugins = [
    BasicPlugin,
    # AWSSQSQueuePlugin
]
