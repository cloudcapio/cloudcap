from __future__ import annotations
from collections import defaultdict
import logging
from typing import Any, cast
import cfn_flip  # type: ignore
import networkx as nx
import abc
from cloudcap.cfn_template import CfnValue, exists_in_cfn_value
import os
import yaml
import json
from cloudcap import utils

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


class ArnBuilder:
    @staticmethod
    def AWSLambdaFunctionArn(
        region: Region, account: Account, function_name: str
    ) -> Arn:
        return f"arn:{region.partition}:lambda:{region}:{account.account_id}:function:{function_name}"

    @staticmethod
    def AWSSQSQueueArn(region: Region, account: Account, queue_name: str) -> Arn:
        return f"arn:{region.partition}:sqs:{region}:{account.account_id}:{queue_name}"


class AWS:
    arns: dict[Arn, Resource]
    deployments: list[Deployment]

    def __init__(self):
        self.arns: dict[Arn, Resource] = dict()
        self.deployments: list[Deployment] = list()

    def add_deployment(self, region: Region, account: Account) -> Deployment:
        d = Deployment(self, region, account)
        self.deployments.append(d)
        return d

    def by_arn(self, arn: Arn) -> Resource:
        try:
            return self.arns[arn]
        except KeyError as e:
            raise UnknownArnError from e

    def new_lambda_function(
        self, region: Region, account: Account, function_name: str
    ) -> AWSLambdaFunction:
        r = AWSLambdaFunction(self, region, account, function_name)
        self.register_resource(r)
        return r

    def new_sqs_queue(
        self, region: Region, account: Account, queue_name: str
    ) -> AWSSQSQueue:
        queue_url = (
            f"https://sqs.{region}.amazonaws.com/{account.account_id}/{queue_name}"
        )
        r = AWSSQSQueue(self, region, account, queue_name, queue_url)
        self.register_resource(r)
        return r

    def register_resource(self, r: Resource) -> None:
        if r.arn in self.arns:
            logger.warning("%s is already a registered resource", r.arn)
        self.arns[r.arn] = r
        logger.info("registered resource %s", r.arn)


class Deployment:
    def __init__(self, aws: AWS, region: Region, account: Account):
        logger.debug("new deployment (%s, %s)", region, account.account_id)
        self.aws = aws
        self.region = region
        self.account = account

    def from_cloudformation_template(self, path: str) -> None:
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


class Resource(abc.ABC):
    def __init__(self, aws: AWS, region: Region, account: Account):
        super().__init__()
        self.aws = aws
        self.region = region
        self.account = account

    @property
    @abc.abstractmethod
    def arn(self) -> Arn:
        raise NotImplementedError


class LambdaEventSource(abc.ABC):
    event_source_mappings: list[LambdaEventSourceMapping]

    def __init__(self) -> None:
        super().__init__()
        self.event_source_mappings = []

    def add_event_source_mapping(
        self, event_source_mapping: LambdaEventSourceMapping
    ) -> None:
        self.event_source_mappings.append(event_source_mapping)


class LambdaEventSourceMapping:
    function_name: str
    event_source_arn: Arn

    def __init__(self, function_name: str, event_source_arn: Arn) -> None:
        self.function_name = function_name
        self.event_source_arn = event_source_arn


class AWSLambdaFunction(Resource):
    def __init__(self, aws: AWS, region: Region, account: Account, function_name: str):
        super().__init__(aws, region, account)
        self.function_name = function_name
        logger.debug("new AWSLambdaFunction: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSLambdaFunctionArn(
            self.region, self.account, self.function_name
        )

    @staticmethod
    def from_cfn(
        aws: AWS, region: Region, account: Account, cfn: Any
    ) -> AWSLambdaFunction:
        raise NotImplementedError


class AWSSQSQueue(Resource, LambdaEventSource):
    aws: AWS
    aws: AWS
    region: Region
    account: Account
    queue_name: str
    queue_url: str

    def __init__(
        self,
        aws: AWS,
        region: Region,
        account: Account,
        queue_name: str,
        queue_url: str,
    ):
        super().__init__(aws, region, account)
        self.queue_name = queue_name
        self.queue_url = queue_url
        self._lambda_triggers = []
        logger.debug("new AWSSQSQueue: %s", self.arn)

    @property
    def arn(self) -> Arn:
        return ArnBuilder.AWSSQSQueueArn(self.region, self.account, self.queue_name)

    @staticmethod
    def from_cfn(aws: AWS, region: Region, account: Account, cfn: Any) -> AWSSQSQueue:
        raise NotImplementedError


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
        match rtype:
            case ResourceTypes.AWS_Lambda_Function:
                prop = body["Properties"]
                function_name: str = ""
                if "QueueName" in prop:
                    function_name = prop["FunctionName"]
                else:
                    function_name = utils.random_id()
                r = self.aws.new_lambda_function(
                    self.region,
                    self.account,
                    function_name,
                )
                self.refs[logical_id] = str(r.arn)
                self.atts[logical_id]["Arn"] = r.function_name
                # INFO:
                # hidden atts:
                #   - SnapStartResponse.ApplyOn
                #   - SnapStartResponse.OptimizationStatus
            case ResourceTypes.AWS_SQS_Queue:
                prop = body["Properties"]
                queue_name: str = ""
                if "QueueName" in prop:
                    queue_name = prop["QueueName"]
                else:
                    queue_name = utils.random_id()
                r = self.aws.new_sqs_queue(
                    self.region,
                    self.account,
                    queue_name,
                )
                self.refs[logical_id] = r.queue_url
                self.atts[logical_id]["Arn"] = str(r.arn)
                self.atts[logical_id]["QueueName"] = r.queue_name
                self.atts[logical_id]["QueueUrl"] = r.queue_url
            case ResourceTypes.AWS_Lambda_EventSourceMapping:
                prop = body["Properties"]
                function_name = prop["FunctionName"]
                event_source_arn = prop["EventSourceArn"]
                mapping = LambdaEventSourceMapping(
                    function_name=function_name, event_source_arn=event_source_arn
                )
                cast(
                    LambdaEventSource, self.aws.by_arn(event_source_arn)
                ).add_event_source_mapping(mapping)
            case _:
                raise UnknownResourceError(f"{rtype}")

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
