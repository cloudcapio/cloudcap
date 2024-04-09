from cloudcap.metrics import NREQUESTS
from cloudcap.plugins import Plugin
from cloudcap.aws import AWSSQSQueue
import logging

logger = logging.getLogger(__name__)

# # INFO: for now, this is implemented directly in Analyzer.constrain
# class BasicPlugin(Plugin):
#     def name(self) -> str:
#         return "builtin_basic_plugin"

#     def constrain(self) -> None:
#         for resource in self.aws.resources:
#             self.add(self[resource, NREQUESTS] >= 0)


class AWSSQSQueuePlugin(Plugin):
    def name(self) -> str:
        return "builtin_aws_sqs_queue_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSSQSQueue):
                self._constrain(resource)

    def _constrain(self, queue: AWSSQSQueue) -> None:
        """
        Constrain one SQS resource
        """
        self._constrain_event_source_mappings(queue)

    def _constrain_event_source_mappings(self, queue: AWSSQSQueue) -> None:
        for mapping in queue.event_source_mappings:
            lambda_function = queue.find_lambda_by_name(mapping.function_name)
            if lambda_function:
                self.add(
                    self[queue, lambda_function, NREQUESTS] == self[queue, NREQUESTS]
                )
            else:
                logger.warning(
                    "event_source_mapping does not map to any existing Lambda: %s",
                    mapping.function_name,
                )


plugins = [AWSSQSQueuePlugin]
