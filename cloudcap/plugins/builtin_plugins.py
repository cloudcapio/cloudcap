from cloudcap.metrics import NREQUESTS
from cloudcap.plugins import Plugin
from cloudcap.aws import AWSSQSQueue, AWSLambdaFunction
import logging

logger = logging.getLogger(__name__)

# # INFO: for now, this is implemented directly in Analyzer.constrain
# class BasicPlugin(Plugin):
#     def name(self) -> str:
#         return "builtin_basic_plugin"

#     def constrain(self) -> None:
#         for resource in self.aws.resources:
#             self.add(self[resource, NREQUESTS] >= 0)


class AWSLambdaFunctionPlugin(Plugin):
    def name(self) -> str:
        return "builtin_aws_lambda_function_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSLambdaFunction):
                self.constrain_one(resource)

    def constrain_one(self, function: AWSLambdaFunction) -> None:
        """
        Constrain one Lambda resource
        """
        self.constrain_environment(function)

    def constrain_environment(self, function: AWSLambdaFunction) -> None:
        """
        Constrain the connections through use of environment variables.
        Not much can be said besides that there is a connection.
        """
        for v in function.environment.values():
            if isinstance(v, str):  # type: ignore
                maybe_resource = self.aws[v]
                if maybe_resource:
                    # can't really constrain much
                    # the only thing is that it may be >= 0
                    # which is generated as a basic constraint by default in Analyzer
                    # this makes sure that the variable is instantiated
                    # so, DON'T REMOVE THIS!!!
                    _ = self[function, maybe_resource, NREQUESTS]
            else:
                logger.warning(
                    "Lambda environment value is not a string (probably an unresolved intrinsic function): %s",
                    v,
                )


class AWSSQSQueuePlugin(Plugin):
    def name(self) -> str:
        return "builtin_aws_sqs_queue_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSSQSQueue):
                self.constrain_one(resource)

    def constrain_one(self, queue: AWSSQSQueue) -> None:
        """
        Constrain one SQS resource
        """
        self.constrain_event_source_mappings(queue)

    def constrain_event_source_mappings(self, queue: AWSSQSQueue) -> None:
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


plugins = [AWSLambdaFunctionPlugin, AWSSQSQueuePlugin]
