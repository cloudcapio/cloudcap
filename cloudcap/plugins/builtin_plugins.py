import re
from collections import defaultdict
from typing import Optional
from cloudcap.metrics import (
    NREQUESTS,
    DYNAMODB_READ,
    DYNAMODB_WRITE,
    S3_GET,
    S3_PUT,
    HTTP_METHODS,
)
from cloudcap.plugins import Plugin
from cloudcap.aws import (
    AWSAPIGatewayMethod,
    AWSAPIGatewayResource,
    AWSAPIGatewayRestApi,
    AWSDynamoDBTable,
    AWSLambdaAlias,
    AWSLambdaFunction,
    AWSSNSSubscription,
    AWSSNSTopic,
    AWSS3Bucket,
    AWSSQSQueue,
    LambdaEventSourceMapping,
)
import logging

logger = logging.getLogger(__name__)


def _extract_lambda_from_integration_uri(uri: str) -> Optional[str]:
    """Pull the Lambda function name or ARN out of an API GW integration URI.

    URI format: arn:*:apigateway:*:lambda:path/2015-03-31/functions/<name-or-arn>/invocations
    """
    match = re.search(r"/functions/([^/]+)/invocations", uri)
    return match.group(1) if match else None


class AWSLambdaFunctionPlugin(Plugin):
    handles = AWSLambdaFunction

    def name(self) -> str:
        return "builtin_aws_lambda_function_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSLambdaFunction):
                self.constrain_one(resource)

    def constrain_one(self, function: AWSLambdaFunction) -> None:
        self.constrain_environment(function)

    def constrain_environment(self, function: AWSLambdaFunction) -> None:
        for v in function.environment.values():
            if isinstance(v, str):  # type: ignore
                try:
                    target = self.aws[v]
                    # Edge variables use the destination resource's message types.
                    # No multiplicity constraint added here — that is application layer.
                    if isinstance(target, AWSDynamoDBTable):
                        _ = self[function, target, DYNAMODB_READ]
                        _ = self[function, target, DYNAMODB_WRITE]
                    elif isinstance(target, AWSS3Bucket):
                        _ = self[function, target, S3_GET]
                        _ = self[function, target, S3_PUT]
                    else:
                        _ = self[function, target, NREQUESTS]
                except KeyError:
                    logger.warning(
                        "Lambda environment value does not map to any existing resource: %s",
                        v,
                    )
            else:
                logger.warning(
                    "Lambda environment value is not a string (probably an unresolved intrinsic function): %s",
                    v,
                )


class AWSLambdaAliasPlugin(Plugin):
    handles = AWSLambdaAlias

    def name(self) -> str:
        return "builtin_aws_lambda_alias_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSLambdaAlias):
                self.constrain_one(resource)

    def constrain_one(self, alias: AWSLambdaAlias) -> None:
        lambda_function = None
        try:
            maybe = self.aws[alias.function_name]
            if isinstance(maybe, AWSLambdaFunction):
                lambda_function = maybe
        except KeyError:
            lambda_function = alias.find_lambda_by_name(alias.function_name)

        if lambda_function:
            # Alias is a transparent proxy: all requests flow through unchanged.
            self.add(self[alias, lambda_function, NREQUESTS] == self[alias, NREQUESTS])
            self.add(
                self[lambda_function, NREQUESTS]
                == self[alias, lambda_function, NREQUESTS]
            )
        else:
            logger.warning(
                "Lambda alias does not map to any existing Lambda function: %s",
                alias.function_name,
            )


class AWSLambdaEventSourceMappingPlugin(Plugin):
    handles = LambdaEventSourceMapping

    def name(self) -> str:
        return "builtin_aws_lambda_event_source_mapping_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, LambdaEventSourceMapping):
                self.constrain_one(resource)

    def constrain_one(self, mapping: LambdaEventSourceMapping) -> None:
        # Mapping is a transparent pass-through: every message from the event
        # source triggers the Lambda exactly once (batch size affects invocation
        # grouping but not total message count at the IaC layer).
        lambda_function = None
        try:
            maybe = self.aws[mapping.function_name]
            if isinstance(maybe, AWSLambdaFunction):
                lambda_function = maybe
        except KeyError:
            lambda_function = mapping.find_lambda_by_name(mapping.function_name)
        if lambda_function:
            self.add(
                self[mapping, lambda_function, NREQUESTS] == self[mapping, NREQUESTS]
            )
        else:
            logger.warning(
                "EventSourceMapping target Lambda not found: %s",
                mapping.function_name,
            )


class AWSSQSQueuePlugin(Plugin):
    handles = AWSSQSQueue

    def name(self) -> str:
        return "builtin_aws_sqs_queue_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSSQSQueue):
                self.constrain_one(resource)

    def constrain_one(self, queue: AWSSQSQueue) -> None:
        self.constrain_event_source_mappings(queue)

    def constrain_event_source_mappings(self, queue: AWSSQSQueue) -> None:
        for mapping in queue.event_source_mappings:
            if queue.deduplicates:
                # FIFO + content-based deduplication: duplicate messages are
                # dropped, so fewer messages reach the mapping than arrive.
                self.add(
                    self[queue, NREQUESTS] >= self[queue, mapping, NREQUESTS]
                )
            else:
                # Standard queue: every message is delivered to the mapping.
                self.add(
                    self[queue, mapping, NREQUESTS] == self[queue, NREQUESTS]
                )


class AWSSNSTopicPlugin(Plugin):
    handles = AWSSNSTopic

    def name(self) -> str:
        return "builtin_aws_sns_topic_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSSNSTopic):
                self.constrain_one(resource)

    def constrain_one(self, topic: AWSSNSTopic) -> None:
        for endpoint in topic.subscriptions:
            try:
                target = self.aws[endpoint]
                # Fan-out: every subscriber receives every message.
                self.add(self[topic, target, NREQUESTS] == self[topic, NREQUESTS])
            except KeyError:
                logger.warning(
                    "SNS topic subscription endpoint does not map to any existing resource: %s",
                    endpoint,
                )


class AWSSNSSubscriptionPlugin(Plugin):
    handles = AWSSNSSubscription

    def name(self) -> str:
        return "builtin_aws_sns_subscription_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSSNSSubscription):
                self.constrain_one(resource)

    def constrain_one(self, subscription: AWSSNSSubscription) -> None:
        try:
            topic = self.aws[subscription.topic_arn]
        except KeyError:
            logger.warning(
                "SNS subscription topic ARN does not map to any existing resource: %s",
                subscription.topic_arn,
            )
            return

        try:
            endpoint = self.aws[subscription.endpoint]
        except KeyError:
            logger.warning(
                "SNS subscription endpoint does not map to any existing resource: %s",
                subscription.endpoint,
            )
            return

        # Fan-out: every subscriber receives every message.
        self.add(self[topic, endpoint, NREQUESTS] == self[topic, NREQUESTS])


class AWSDynamoDBTablePlugin(Plugin):
    handles = AWSDynamoDBTable

    def name(self) -> str:
        return "builtin_aws_dynamodb_table_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSDynamoDBTable):
                self.constrain_one(resource)

    def constrain_one(self, table: AWSDynamoDBTable) -> None:
        # DynamoDB has separate read and write message types per the paper.
        # No outgoing edges — it is a passive sink.
        _ = self[table, DYNAMODB_READ]
        _ = self[table, DYNAMODB_WRITE]


class AWSS3BucketPlugin(Plugin):
    handles = AWSS3Bucket

    def name(self) -> str:
        return "builtin_aws_s3_bucket_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSS3Bucket):
                self.constrain_one(resource)

    def constrain_one(self, bucket: AWSS3Bucket) -> None:
        # S3 has separate read (GET) and write (PUT) message types, analogous
        # to DynamoDB. It is a passive sink with no outgoing dataflow edges.
        _ = self[bucket, S3_GET]
        _ = self[bucket, S3_PUT]


class AWSAPIGatewayRestApiPlugin(Plugin):
    handles = AWSAPIGatewayRestApi

    def name(self) -> str:
        return "builtin_aws_apigateway_restapi_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSAPIGatewayRestApi):
                self.constrain_one(resource)

    def constrain_one(self, api: AWSAPIGatewayRestApi) -> None:
        # Find all Method nodes that belong to this RestApi.
        methods = [
            r
            for r in self.aws.arns.values()
            if isinstance(r, AWSAPIGatewayMethod) and r.rest_api_arn == api.arn
        ]

        # Collect one node variable per distinct HTTP method type on this API.
        method_vars: dict[str, object] = {}
        for method in methods:
            if method.http_method in HTTP_METHODS:
                method_vars[method.http_method] = self[api, method.http_method]

        # Intrinsic: api.NREQUESTS = api.GET + api.POST + ...
        if method_vars:
            vars_list = list(method_vars.values())
            self.add(self[api, NREQUESTS] == sum(vars_list[1:], vars_list[0]))


class AWSAPIGatewayResourcePlugin(Plugin):
    handles = AWSAPIGatewayResource

    def name(self) -> str:
        return "builtin_aws_apigateway_resource_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSAPIGatewayResource):
                self.constrain_one(resource)

    def constrain_one(self, resource: AWSAPIGatewayResource) -> None:
        # A path-segment resource is a transparent structural node.
        # Instantiate its node variable; the Analyzer handles incoming constraints.
        _ = self[resource, NREQUESTS]


class AWSAPIGatewayMethodPlugin(Plugin):
    handles = AWSAPIGatewayMethod

    def name(self) -> str:
        return "builtin_aws_apigateway_method_plugin"

    def constrain(self) -> None:
        for resource in self.aws.arns.values():
            if isinstance(resource, AWSAPIGatewayMethod):
                self.constrain_one(resource)

    def constrain_one(self, method: AWSAPIGatewayMethod) -> None:
        # Intrinsic: a Method handles exactly one HTTP verb, so its total
        # request count equals that verb's request count.
        if method.http_method in HTTP_METHODS:
            self.add(self[method, NREQUESTS] == self[method, method.http_method])

        # Outgoing: route all requests to the Lambda integration target.
        if method.integration_uri:
            name_or_arn = _extract_lambda_from_integration_uri(method.integration_uri)
            if name_or_arn:
                lambda_resource = None
                try:
                    lambda_resource = self.aws[name_or_arn]
                except KeyError:
                    lambda_resource = method.find_lambda_by_name(name_or_arn)

                if lambda_resource:
                    self.add(
                        self[method, lambda_resource, NREQUESTS]
                        == self[method, NREQUESTS]
                    )
                else:
                    logger.warning(
                        "API Gateway Method integration target not found: %s",
                        name_or_arn,
                    )


plugins = [
    AWSLambdaFunctionPlugin,
    AWSLambdaAliasPlugin,
    AWSLambdaEventSourceMappingPlugin,
    AWSSQSQueuePlugin,
    AWSSNSTopicPlugin,
    AWSSNSSubscriptionPlugin,
    AWSDynamoDBTablePlugin,
    AWSS3BucketPlugin,
    AWSAPIGatewayRestApiPlugin,
    AWSAPIGatewayResourcePlugin,
    AWSAPIGatewayMethodPlugin,
]
