from __future__ import annotations
from collections import defaultdict
import logging
import re
import sys
from typing import Any, Optional, cast
import cfn_flip  # type: ignore
import networkx as nx
import abc

from cloudcap import INVALID_INPUT
from cloudcap.cfn_template import CfnValue, exists_in_cfn_value
import os
import yaml
import json

logger = logging.getLogger(__name__)


class UnknownArnError(Exception):
    pass


class UnknownResourceError(Exception):
    pass


class InvalidCloudFormationTemplate(Exception):
    pass


##### Account


class Account:
    def __init__(self, account_id: str):
        self.account_id = account_id


##### Regions and Partitions


class Partition:
    def __init__(self, partition: str):
        self.partition = partition

    def __str__(self):
        return self.partition

    def __repr__(self):
        return str(self)


class Partitions:
    aws = Partition("aws")


class Region:
    def __init__(self, partition: Partition, region: str):
        self.partition = partition
        self.region = region

    def __str__(self):
        return self.region

    def __repr__(self):
        return str(self)


class Regions:
    us_east_1 = Region(Partitions.aws, "us-east-1")
    us_east_2 = Region(Partitions.aws, "us-east-2")


##### Arn

Arn = str
Url = str


class ArnBuilder:
    @staticmethod
    def AWSLambdaFunctionArn(
        region: Region, account: Account, function_name: str
    ) -> Arn:
        return f"arn:{region.partition}:lambda:{region}:{account.account_id}:function:{function_name}"

    @staticmethod
    def AWSSQSQueueArn(region: Region, account: Account, queue_name: str) -> Arn:
        return f"arn:{region.partition}:sqs:{region}:{account.account_id}:{queue_name}"

    @staticmethod
    def AWSLambdaAliasArn(
        region: Region, account: Account, function_name: str, alias_name: str
    ) -> Arn:
        return f"arn:{region.partition}:lambda:{region}:{account.account_id}:function:{function_name}:{alias_name}"

    @staticmethod
    def AWSSNSTopicArn(region: Region, account: Account, topic_name: str) -> Arn:
        return f"arn:{region.partition}:sns:{region}:{account.account_id}:{topic_name}"

    @staticmethod
    def AWSDynamoDBTableArn(region: Region, account: Account, table_name: str) -> Arn:
        return f"arn:{region.partition}:dynamodb:{region}:{account.account_id}:table/{table_name}"

    @staticmethod
    def AWSAPIGatewayArn(region: Region, account: Account, api_name: str) -> Arn:
        return f"arn:{region.partition}:execute-api:{region}:{account.account_id}:{api_name}"

    @staticmethod
    def AWSS3BucketArn(bucket_name: str) -> Arn:
        return f"arn:aws:s3:::{bucket_name}"

    @staticmethod
    def AWSLambdaEventSourceMappingArn(
        region: Region, account: Account, logical_id: str
    ) -> Arn:
        return f"arn:{region.partition}:lambda:{region}:{account.account_id}:event-source-mapping:{logical_id}"

    @staticmethod
    def AWSKinesisStreamArn(region: Region, account: Account, stream_name: str) -> Arn:
        return f"arn:{region.partition}:kinesis:{region}:{account.account_id}:stream/{stream_name}"

    @staticmethod
    def AWSStepFunctionsStateMachineArn(region: Region, account: Account, name: str) -> Arn:
        return f"arn:{region.partition}:states:{region}:{account.account_id}:stateMachine:{name}"


class AWS:
    arns: dict[Arn, Resource]
    urls: dict[Url, Resource]
    deployments: list[Deployment]
    # TODO: this is a temporary mapping of logical_id to Resource
    logical_id_to_resource: dict[str, Resource]

    def __init__(self):
        self.arns = {}
        self.urls = {}
        self.deployments = []
        self.logical_id_to_resource = {}

    @property
    def resources(self) -> list[Resource]:
        return list(self.arns.values())

    def add_deployment(self, region: Region, account: Account) -> Deployment:
        d = Deployment(self, region, account)
        self.deployments.append(d)
        return d

    def __getitem__(self, key: Arn | Url) -> Resource:
        if not (isinstance(key, Arn) or isinstance(key, Url)):  # type: ignore
            raise KeyError(
                f"AWS.__getitem__ expected an Arn or Url, but got a {type(key)}. Got: {key}"
            )

        try:
            return self.arns[key]
        except KeyError:
            try:
                return self.urls[key]
            except KeyError:
                raise KeyError(f"AWS.__getitem__ received unknown key: {key}")

    def register_resource(self, r: Resource) -> None:
        if r.arn in self.arns:
            logger.warning("%s is already a registered resource", r.arn)
        self.arns[r.arn] = r
        logger.info("registered resource %s", r.arn)

    def register_url(self, url: Url, r: Resource) -> None:
        if url in self.urls:
            logger.warning("%s is already a registered URL", url)
        self.urls[url] = r
        logger.info("registered url for %s: %s", r.arn, url)


class Deployment:
    def __init__(self, aws: AWS, region: Region, account: Account):
        logger.debug("new deployment (%s, %s)", region, account.account_id)
        self.aws = aws
        self.region = region
        self.account = account

    def from_cloudformation_template(self, path: str) -> None:
        from cloudcap.resource_cache import load_all as load_cached_resource_classes
        for cls in load_cached_resource_classes():
            register_resource_class(cls)
        CloudFormationStack.from_file(self.aws, self.region, self.account, path)


##### Resources


class ResourceTypes:
    AWS_S3_Bucket = "AWS::S3::Bucket"
    AWS_SQS_Queue = "AWS::SQS::Queue"
    AWS_Lambda_Function = "AWS::Lambda::Function"
    AWS_Lambda_Alias = "AWS::Lambda::Alias"
    AWS_Lambda_EventSourceMapping = "AWS::Lambda::EventSourceMapping"
    AWS_Serverless_Function = "AWS::Serverless::Function"
    AWS_SNS_Subscription = "AWS::SNS::Subscription"
    AWS_SNS_Topic = "AWS::SNS::Topic"
    AWS_DynamoDB_Table = "AWS::DynamoDB::Table"
    AWS_ApiGateway_RestApi = "AWS::ApiGateway::RestApi"
    AWS_ApiGateway_Resource = "AWS::ApiGateway::Resource"
    AWS_ApiGateway_Method = "AWS::ApiGateway::Method"

    AWS_ApiGateway_Deployment = "AWS::ApiGateway::Deployment"
    AWS_S3_BucketPolicy = "AWS::S3::BucketPolicy"
    AWS_Lambda_Permission = "AWS::Lambda::Permission"
    AWS_SQS_QueuePolicy = "AWS::SQS::QueuePolicy"
    AWS_SNS_TopicPolicy = "AWS::SNS::TopicPolicy"
    AWS_IAM_Role = "AWS::IAM::Role"
    AWS_IAM_Policy = "AWS::IAM::Policy"
    AWS_IAM_AccessKey = "AWS::IAM::AccessKey"
    AWS_IAM_Group = "AWS::IAM::Group"
    AWS_IAM_GroupPolicy = "AWS::IAM::GroupPolicy"
    AWS_IAM_InstanceProfile = "AWS::IAM::InstanceProfile"
    AWS_IAM_ManagedPolicy = "AWS::IAM::ManagedPolicy"
    AWS_IAM_OIDCProvider = "AWS::IAM::OIDCProvider"
    AWS_IAM_RolePolicy = "AWS::IAM::RolePolicy"
    AWS_IAM_SAMLProvider = "AWS::IAM::SAMLProvider"
    AWS_IAM_ServerCertificate = "AWS::IAM::ServerCertificate"
    AWS_IAM_ServiceLinkedRole = "AWS::IAM::ServiceLinkedRole"
    AWS_IAM_User = "AWS::IAM::User"
    AWS_IAM_UserPolicy = "AWS::IAM::UserPolicy"
    AWS_IAM_UserToGroupAddition = "AWS::IAM::UserToGroupAddition"
    AWS_IAM_VirtualMFADevice = "AWS::IAM::VirtualMFADevice"
    AWS_CDK_Metadata = "AWS::CDK::Metadata"
    AWS_Kinesis_Stream = "AWS::Kinesis::Stream"
    AWS_StepFunctions_StateMachine = "AWS::StepFunctions::StateMachine"


class Resource(abc.ABC):
    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        logical_id: Optional[str] = None,
    ):
        super().__init__()
        self.aws = aws
        self.region = region
        self.account = account
        self.logical_id = logical_id
        self.aws.register_resource(self)

    @property
    @abc.abstractmethod
    def arn(self) -> Arn:
        raise NotImplementedError

    # TODO this could be a fxn name or an ARN or (https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-lambda-eventsourcemapping.html#cfn-lambda-eventsourcemapping-functionname)
    def find_lambda_by_name(self, lambda_name: str) -> Optional[AWSLambdaFunction]:
        """
        Finding Lambda by name is a common thing.
        This will find the ARN of the Lambda with this name within the same region and account.
        """
        lambda_arn = ArnBuilder.AWSLambdaFunctionArn(
            self.region, self.account, lambda_name
        )
        if lambda_arn in self.aws.arns:
            return cast(AWSLambdaFunction, self.aws[lambda_arn])
        else:
            return None


class LambdaEventSource(abc.ABC):
    event_source_mappings: list[LambdaEventSourceMapping]

    def __init__(self) -> None:
        super().__init__()
        self.event_source_mappings = []

    def add_event_source_mapping(
        self, event_source_mapping: LambdaEventSourceMapping
    ) -> None:
        self.event_source_mappings.append(event_source_mapping)


class LambdaEventSourceMapping(Resource):
    cfn_type = "AWS::Lambda::EventSourceMapping"
    function_name: str
    event_source_arn: Arn

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        function_name: str,
        event_source_arn: Arn,
        logical_id: Optional[str] = None,
    ) -> None:
        self.function_name = function_name
        self.event_source_arn = event_source_arn
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new LambdaEventSourceMapping: %s", self.arn)

    @property
    def arn(self) -> Arn:
        suffix = self.logical_id if self.logical_id is not None else self.function_name
        return ArnBuilder.AWSLambdaEventSourceMappingArn(
            self.region, self.account, suffix
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> LambdaEventSourceMapping:
        prop = body["Properties"]
        function_name = prop["FunctionName"]
        event_source_arn = prop["EventSourceArn"]
        assert isinstance(function_name, str)
        assert isinstance(event_source_arn, str)
        mapping = LambdaEventSourceMapping(
            aws=stack.aws,
            region=stack.region,
            account=stack.account,
            function_name=function_name,
            event_source_arn=event_source_arn,
            logical_id=logical_id,
        )
        cast(LambdaEventSource, stack.aws[event_source_arn]).add_event_source_mapping(
            mapping
        )
        stack.refs[logical_id] = str(mapping.arn)
        return mapping


class AWSLambdaFunction(Resource):
    cfn_type = "AWS::Lambda::Function"
    function_name: str
    # A function's environment variable settings
    environment: dict[str, str]

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        function_name: str,
        environment: Optional[dict[str, str]] = None,
        logical_id: Optional[str] = None,
    ):
        self.function_name = function_name
        self.environment = environment if environment else {}
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSLambdaFunction: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSLambdaFunctionArn(
            self.region, self.account, self.function_name
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSLambdaFunction:
        prop = body["Properties"]

        # if "FunctionName" not in prop:
        #     logger.error(
        #         "To use cloudcap, FunctionName is a required parameter for AWS::Lambda::Function resource type."
        #     )
        #     sys.exit(INVALID_INPUT)

        function_name: str = prop["FunctionName"]
        environment: Optional[dict[str, str]] = (
            prop["Environment"] if "Environment" in prop else None
        )

        r = AWSLambdaFunction(
            stack.aws,
            stack.region,
            stack.account,
            function_name,
            environment=environment,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["Arn"] = str(r.arn)
        # INFO:
        # hidden atts:
        #   - SnapStartResponse.ApplyOn
        #   - SnapStartResponse.OptimizationStatus
        return r


class AWSLambdaAlias(Resource):
    cfn_type = "AWS::Lambda::Alias"
    function_name: str
    alias_name: str
    function_version: str

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        function_name: str,
        alias_name: str,
        function_version: str,
        logical_id: Optional[str] = None,
    ):
        self.function_name = function_name
        self.alias_name = alias_name
        self.function_version = function_version
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSLambdaAlias: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSLambdaAliasArn(
            self.region, self.account, self.function_name, self.alias_name
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSLambdaAlias:
        prop = body["Properties"]
        function_name = prop["FunctionName"]
        alias_name = prop["Name"]
        function_version = prop["FunctionVersion"]
        assert isinstance(function_name, str)
        assert isinstance(alias_name, str)
        assert isinstance(function_version, str)
        r = AWSLambdaAlias(
            stack.aws,
            stack.region,
            stack.account,
            function_name,
            alias_name,
            function_version,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["Arn"] = str(r.arn)
        stack.atts[logical_id]["Name"] = r.alias_name
        return r


class AWSSNSTopic(Resource):
    cfn_type = "AWS::SNS::Topic"
    topic_name: str
    subscriptions: list[str]

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        topic_name: str,
        subscriptions: Optional[list[str]] = None,
        logical_id: Optional[str] = None,
    ):
        self.topic_name = topic_name
        self.subscriptions = subscriptions if subscriptions else []
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSSNSTopic: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSSNSTopicArn(self.region, self.account, self.topic_name)

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSSNSTopic:
        prop = body["Properties"]
        topic_name = prop["TopicName"] if "TopicName" in prop else logical_id
        subscriptions_raw = prop["Subscription"] if "Subscription" in prop else []
        assert isinstance(topic_name, str)
        assert isinstance(subscriptions_raw, list)
        subscriptions: list[str] = []
        for sub in subscriptions_raw:
            if isinstance(sub, dict) and "Endpoint" in sub:
                endpoint = sub["Endpoint"]
                if isinstance(endpoint, str):
                    subscriptions.append(endpoint)
        r = AWSSNSTopic(
            stack.aws,
            stack.region,
            stack.account,
            topic_name,
            subscriptions=subscriptions,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["Arn"] = str(r.arn)
        return r


class AWSSNSSubscription(Resource):
    cfn_type = "AWS::SNS::Subscription"
    topic_arn: str
    protocol: str
    endpoint: str

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        topic_arn: str,
        protocol: str,
        endpoint: str,
        logical_id: Optional[str] = None,
    ):
        self.topic_arn = topic_arn
        self.protocol = protocol
        self.endpoint = endpoint
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSSNSSubscription: %s", self.arn)

    @property
    def arn(self) -> Arn:
        suffix = self.logical_id if self.logical_id is not None else self.endpoint
        return (
            f"arn:{self.region.partition}:sns:{self.region}:"
            f"{self.account.account_id}:subscription:{suffix}"
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSSNSSubscription:
        prop = body["Properties"]
        topic_arn = prop["TopicArn"]
        protocol = prop["Protocol"]
        endpoint = prop["Endpoint"]
        assert isinstance(topic_arn, str)
        assert isinstance(protocol, str)
        assert isinstance(endpoint, str)
        r = AWSSNSSubscription(
            stack.aws,
            stack.region,
            stack.account,
            topic_arn,
            protocol,
            endpoint,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["Arn"] = str(r.arn)
        return r


class AWSLambdaPermission(Resource):
    function_name: str
    principal: str
    source_arn: Optional[str]

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        function_name: str,
        principal: str,
        source_arn: Optional[str] = None,
        logical_id: Optional[str] = None,
    ):
        self.function_name = function_name
        self.principal = principal
        self.source_arn = source_arn
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSLambdaPermission: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return (
            f"arn:{self.region.partition}:lambda:{self.region}:"
            f"{self.account.account_id}:permission:{self.function_name}:{self.principal}"
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSLambdaPermission:
        prop = body["Properties"]
        function_name = prop["FunctionName"]
        principal = prop["Principal"]
        source_arn = prop.get("SourceArn", None)
        assert isinstance(function_name, str)
        assert isinstance(principal, str)
        assert source_arn is None or isinstance(source_arn, str)
        r = AWSLambdaPermission(
            stack.aws,
            stack.region,
            stack.account,
            function_name,
            principal,
            source_arn=source_arn,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = str(r.arn)
        return r


class AWSDynamoDBTable(Resource):
    cfn_type = "AWS::DynamoDB::Table"
    table_name: str

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        table_name: str,
        logical_id: Optional[str] = None,
    ):
        self.table_name = table_name
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSDynamoDBTable: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSDynamoDBTableArn(
            self.region, self.account, self.table_name
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSDynamoDBTable:
        prop = body["Properties"]
        table_name = prop["TableName"] if "TableName" in prop else logical_id
        assert isinstance(table_name, str)
        r = AWSDynamoDBTable(
            stack.aws,
            stack.region,
            stack.account,
            table_name,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = table_name
        stack.atts[logical_id]["Arn"] = str(r.arn)
        stack.atts[logical_id]["Name"] = r.table_name
        return r


class AWSAPIGatewayRestApi(Resource):
    cfn_type = "AWS::ApiGateway::RestApi"
    api_name: str

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        api_name: str,
        logical_id: Optional[str] = None,
    ):
        self.api_name = api_name
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSAPIGatewayRestApi: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSAPIGatewayArn(self.region, self.account, self.api_name)

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSAPIGatewayRestApi:
        prop = body["Properties"]
        api_name = prop.get("Name", logical_id)
        assert isinstance(api_name, str)
        r = AWSAPIGatewayRestApi(
            stack.aws, stack.region, stack.account, api_name, logical_id=logical_id
        )
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["RootResourceId"] = logical_id
        return r


class AWSAPIGatewayResource(Resource):
    cfn_type = "AWS::ApiGateway::Resource"
    rest_api_arn: Arn
    path_part: str

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        rest_api_arn: Arn,
        path_part: str,
        logical_id: Optional[str] = None,
    ):
        self.rest_api_arn = rest_api_arn
        self.path_part = path_part
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSAPIGatewayResource: %s", self.arn)

    @property
    def arn(self) -> Arn:
        suffix = self.logical_id if self.logical_id is not None else self.path_part
        return (
            f"arn:{self.region.partition}:execute-api:{self.region}:"
            f"{self.account.account_id}:resource:{suffix}"
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSAPIGatewayResource:
        prop = body["Properties"]
        rest_api_arn = prop.get("RestApiId", "")
        path_part = prop.get("PathPart", logical_id)
        assert isinstance(rest_api_arn, str)
        assert isinstance(path_part, str)
        r = AWSAPIGatewayResource(
            stack.aws,
            stack.region,
            stack.account,
            rest_api_arn,
            path_part,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["ResourceId"] = str(r.arn)
        return r


class AWSAPIGatewayMethod(Resource):
    cfn_type = "AWS::ApiGateway::Method"
    rest_api_arn: Arn
    http_method: str
    integration_uri: Optional[str]

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        rest_api_arn: Arn,
        http_method: str,
        integration_uri: Optional[str] = None,
        logical_id: Optional[str] = None,
    ):
        self.rest_api_arn = rest_api_arn
        self.http_method = http_method.upper()
        self.integration_uri = integration_uri
        super().__init__(aws, region, account, logical_id=logical_id)
        logger.debug("new AWSAPIGatewayMethod: %s", self.arn)

    @property
    def arn(self) -> Arn:
        suffix = self.logical_id if self.logical_id is not None else self.http_method
        return (
            f"arn:{self.region.partition}:execute-api:{self.region}:"
            f"{self.account.account_id}:method:{suffix}"
        )

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSAPIGatewayMethod:
        prop = body["Properties"]
        rest_api_arn = prop.get("RestApiId", "")
        http_method = prop.get("HttpMethod", "")
        integration = prop.get("Integration", {})
        integration_uri: Optional[str] = None
        if isinstance(integration, dict):
            uri = integration.get("Uri")
            if isinstance(uri, str):
                integration_uri = uri
        assert isinstance(rest_api_arn, str)
        assert isinstance(http_method, str)
        r = AWSAPIGatewayMethod(
            stack.aws,
            stack.region,
            stack.account,
            rest_api_arn,
            http_method,
            integration_uri=integration_uri,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = str(r.arn)
        return r


class AWSS3Bucket(Resource):
    cfn_type = "AWS::S3::Bucket"
    bucket_name: str

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        bucket_name: str,
        logical_id: Optional[str] = None,
    ):
        self.bucket_name = bucket_name
        super().__init__(aws, region, account, logical_id=logical_id)
        # Register bucket name so Lambda env vars referencing it by name are found.
        aws.register_url(bucket_name, self)
        logger.debug("new AWSS3Bucket: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSS3BucketArn(self.bucket_name)

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSS3Bucket:
        prop = body["Properties"]
        bucket_name = prop.get("BucketName", logical_id)
        assert isinstance(bucket_name, str)
        r = AWSS3Bucket(
            stack.aws, stack.region, stack.account, bucket_name, logical_id=logical_id
        )
        stack.refs[logical_id] = r.bucket_name
        stack.atts[logical_id]["Arn"] = str(r.arn)
        stack.atts[logical_id]["DomainName"] = f"{r.bucket_name}.s3.amazonaws.com"
        return r


class AWSSQSQueue(Resource, LambdaEventSource):
    cfn_type = "AWS::SQS::Queue"
    aws: AWS
    region: Region
    account: Account
    queue_name: str
    queue_url: Url
    fifo_queue: bool
    content_based_deduplication: bool

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        queue_name: str,
        fifo_queue: bool = False,
        content_based_deduplication: bool = False,
        logical_id: Optional[str] = None,
    ):
        self.queue_name = queue_name
        self.fifo_queue = fifo_queue
        self.content_based_deduplication = content_based_deduplication
        self.queue_url = (
            f"https://sqs.{region}.amazonaws.com/{account.account_id}/{queue_name}"
        )
        super().__init__(aws, region, account, logical_id=logical_id)
        self.aws.register_url(self.queue_url, self)
        logger.debug("new AWSSQSQueue: %s. URL: %s", self.arn, self.queue_url)

    @property
    def deduplicates(self) -> bool:
        return self.fifo_queue and self.content_based_deduplication

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSSQSQueueArn(self.region, self.account, self.queue_name)

    @staticmethod
    def from_cloudformation_stack(
        stack: CloudFormationStack, logical_id: str, body: CfnValue
    ) -> AWSSQSQueue:
        prop = body["Properties"]
        queue_name: str = prop["QueueName"]
        fifo_queue: bool = bool(prop.get("FifoQueue", False))
        content_based_deduplication: bool = bool(
            prop.get("ContentBasedDeduplication", False)
        )
        r = AWSSQSQueue(
            stack.aws,
            stack.region,
            stack.account,
            queue_name,
            fifo_queue=fifo_queue,
            content_based_deduplication=content_based_deduplication,
            logical_id=logical_id,
        )
        stack.refs[logical_id] = r.queue_url
        stack.atts[logical_id]["Arn"] = str(r.arn)
        stack.atts[logical_id]["QueueName"] = r.queue_name
        stack.atts[logical_id]["QueueUrl"] = r.queue_url
        return r


class AWSKinesisStream(Resource, LambdaEventSource):
    cfn_type = "AWS::Kinesis::Stream"
    stream_name: str

    def __init__(self, aws: AWS, region: Region, account: Account, stream_name: str, logical_id: Optional[str] = None) -> None:
        self.stream_name = stream_name
        super().__init__(aws, region, account, logical_id=logical_id)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSKinesisStreamArn(self.region, self.account, self.stream_name)

    @staticmethod
    def from_cloudformation_stack(stack: CloudFormationStack, logical_id: str, body: CfnValue) -> AWSKinesisStream:
        prop = body.get("Properties", {})
        stream_name = prop.get("Name", logical_id)
        assert isinstance(stream_name, str)
        r = AWSKinesisStream(stack.aws, stack.region, stack.account, stream_name, logical_id=logical_id)
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["Arn"] = str(r.arn)
        return r


class AWSStepFunctionsStateMachine(Resource):
    cfn_type = "AWS::StepFunctions::StateMachine"
    name: str

    def __init__(self, aws: AWS, region: Region, account: Account, name: str, logical_id: Optional[str] = None) -> None:
        self.name = name
        super().__init__(aws, region, account, logical_id=logical_id)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSStepFunctionsStateMachineArn(self.region, self.account, self.name)

    @staticmethod
    def from_cloudformation_stack(stack: CloudFormationStack, logical_id: str, body: CfnValue) -> AWSStepFunctionsStateMachine:
        prop = body.get("Properties", {})
        name = prop.get("StateMachineName", logical_id)
        assert isinstance(name, str)
        r = AWSStepFunctionsStateMachine(stack.aws, stack.region, stack.account, name, logical_id=logical_id)
        stack.refs[logical_id] = str(r.arn)
        stack.atts[logical_id]["Arn"] = str(r.arn)
        return r


_dynamic_resource_registry: dict[str, type[Resource]] = {}


def register_resource_class(cls: type[Resource]) -> None:
    if hasattr(cls, "cfn_type"):
        _dynamic_resource_registry[cls.cfn_type] = cls


##### CloudFormation
class CloudFormationTemplateError(Exception):
    pass


class CloudFormationStack:
    """A CloudFormation Stack, usually instantiated from a CloudFormation template file."""

    aws: AWS
    region: Region
    account: Account
    template: CfnValue
    path: str | os.PathLike[Any]
    dependency_graph: nx.DiGraph
    resources: list[CfnValue]
    logical_ids_by_dependency_order: list[str]
    refs: dict[str, str]
    atts: defaultdict[str, dict[str, str]]

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        template: CfnValue,
        path: str | os.PathLike[Any] = "",
    ):
        self.aws = aws
        self.region = region
        self.account = account
        self.template = template
        self.path = path
        self.refs = {}
        self.atts = defaultdict(lambda: {})
        self._init_dependency_graph()
        # instantiate the resources in order, and register them at aws
        resources = self.template["Resources"]
        for logical_id in self.logical_ids_by_dependency_order:
            self.create_resource(logical_id, resources[logical_id])

    def _init_dependency_graph(self) -> None:
        self.dependency_graph = nx.DiGraph()
        resources = self.template["Resources"]
        for r in resources:
            self.dependency_graph.add_node(r)  # type: ignore

        for r1 in resources:
            for r2, r2_body in resources.items():
                if exists_in_cfn_value(r2_body, r1):
                    self.dependency_graph.add_edge(r1, r2)  # type: ignore

        try:
            self.logical_ids_by_dependency_order: list[str] = list(
                nx.topological_sort(self.dependency_graph)  # type: ignore
            )
        except nx.NetworkXUnfeasible as e:
            raise CloudFormationTemplateError(
                f"CloudFormation template is cyclic: {self.path}"
            ) from e

        logger.debug(
            "CloudFormation template (%s) dependency graph: %s",
            self.path,
            self.dependency_graph.edges,
        )

        logger.debug(
            "CloudFormation template (%s) dependency order: %s",
            self.path,
            self.logical_ids_by_dependency_order,
        )

    def create_resource(self, logical_id: str, body: CfnValue) -> None:
        body = self.resolve_intrinsic_functions(body)
        rtype = body["Type"]
        assert isinstance(rtype, str)

        if rtype in _dynamic_resource_registry:
            cls = _dynamic_resource_registry[rtype]
            try:
                self.aws.logical_id_to_resource[logical_id] = cls.from_cloudformation_stack(self, logical_id, body)
            except Exception as e:
                logger.warning("Failed to parse %s (%s): %s", logical_id, rtype, e)
            return

        match rtype:
            case ResourceTypes.AWS_Lambda_Function | ResourceTypes.AWS_Serverless_Function:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSLambdaFunction.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_Lambda_Alias:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSLambdaAlias.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_SQS_Queue:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSSQSQueue.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_SNS_Topic:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSSNSTopic.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_SNS_Subscription:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSSNSSubscription.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_Lambda_Permission:
                pass  # non-dataflow resource, intentionally omitted from graph
            case ResourceTypes.AWS_DynamoDB_Table:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSDynamoDBTable.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_Lambda_EventSourceMapping:
                self.aws.logical_id_to_resource[logical_id] = (
                    LambdaEventSourceMapping.from_cloudformation_stack(
                        self, logical_id, body
                    )
                )
            case ResourceTypes.AWS_S3_Bucket:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSS3Bucket.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_ApiGateway_RestApi:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSAPIGatewayRestApi.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_ApiGateway_Resource:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSAPIGatewayResource.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_ApiGateway_Method:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSAPIGatewayMethod.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_Kinesis_Stream:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSKinesisStream.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_StepFunctions_StateMachine:
                self.aws.logical_id_to_resource[logical_id] = (
                    AWSStepFunctionsStateMachine.from_cloudformation_stack(self, logical_id, body)
                )
            case ResourceTypes.AWS_ApiGateway_Deployment | ResourceTypes.AWS_S3_BucketPolicy:
                pass  # non-dataflow, no constraints
            case _:
                logger.warning("Skipping unsupported resource type: %s", rtype)

    def resolve_intrinsic_functions(self, body: CfnValue) -> CfnValue:
        """
        Maps intrinsic functions within a CloudFormation template body.

        Args:
        - body (CfnValue): The CloudFormation template body containing intrinsic functions.

        Returns:
        - CfnValue: The CloudFormation template body with resolved intrinsic functions.
        """

        # define a function that recursely searches for the intrinsic functions
        # and replaces them
        def rec(_body: CfnValue) -> CfnValue:
            if isinstance(_body, dict):
                # Recursively search in each value of the dictionary
                _body = cast(dict[str, CfnValue], _body)
                for k, v in _body.items():
                    if k == "Ref":
                        # v is the logical id
                        return self.refs[v]
                    elif k == "Fn::GetAtt":
                        try:
                            logical_id = v[0]
                            attribute_name = v[1]
                        except Exception as e:
                            raise InvalidCloudFormationTemplate from e
                        return self.atts[logical_id][attribute_name]
                for k, v in _body.items():
                    _body[k] = rec(v)
                return _body
            elif isinstance(_body, list):
                # Recursively search in each element of the list
                return [rec(v) for v in cast(list[CfnValue], _body)]
            # can immediately if it is just a str
            return _body

        body = rec(body)
        return body

    @classmethod
    def from_file(
        cls, aws: AWS, region: Region, account: Account, path: str | os.PathLike[Any]
    ) -> CloudFormationStack:
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = cfn_flip.load_yaml(f)  # type: ignore
                logger.info("Loaded %s as CloudFormation template in YAML format", path)
            except yaml.YAMLError:
                try:
                    data = cfn_flip.load_json(f)  # type: ignore
                    logger.info(
                        "Loaded %s as a CloudFormation template in JSON format", path
                    )
                except json.JSONDecodeError:
                    # pylint: disable=raise-missing-from
                    raise CloudFormationTemplateError(
                        f"Unable to load {path} as a CloudFormation template"
                    )

        return cls(aws, region, account, data, path)
