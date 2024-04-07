from __future__ import annotations
import logging
from typing import Any
import cfn_flip  # type: ignore
import networkx as nx
import abc
from cloudcap.cfn_template import CfnValue, exists_in_cfn_value
import os

logger = logging.getLogger(__name__)


class UnknownArnError(Exception):
    pass


class UnknownResourceError(Exception):
    pass


##### Account


class Account:
    def __init__(self, id: str):
        self.id = id


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


class Arn:
    def __init__(self, arn: str):
        self.arn = arn

    def __str__(self):
        return self.arn

    def __repr__(self):
        return self.arn

    @staticmethod
    def AWSLambdaFunctionArn(
        region: Region, account: Account, function_name: str
    ) -> Arn:
        return Arn(
            f"arn:{region.partition}:lambda:{region}:{account.id}:function:{function_name}"
        )

    @staticmethod
    def AWSSQSQueueArn(region: Region, account: Account, queue_name: str) -> Arn:
        return Arn(f"arn:{region.partition}:sqs:{region}:{account.id}:{queue_name}")


class AWS:
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
            raise UnknownArnError(e)

    def new_lambda_function(
        self, region: Region, account: Account, function_name: str
    ) -> Resource:
        r = AWSLambdaFunction(self, region, account, function_name)
        self.register_resource(r)
        return r

    def new_sqs_queue(
        self, region: Region, account: Account, queue_name: str
    ) -> Resource:
        r = AWSSQSQueue(self, region, account, queue_name)
        self.register_resource(r)
        return r

    def register_resource(self, r: Resource) -> None:
        if r.arn in self.arns:
            logger.warn(f"{r.arn} is already a registered resource")
        self.arns[r.arn] = r
        logger.info(f"registered resource {r.arn}")


class Deployment:
    def __init__(self, aws: AWS, region: Region, account: Account):
        logger.debug(f"new deployment ({region}, {account.id})")
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
        self.aws = aws
        self.region = region
        self.account = account

    @property
    @abc.abstractmethod
    def arn(self) -> Arn:
        raise NotImplementedError("Resource must implement arn() method")


class AWSLambdaFunction(Resource):
    def __init__(self, aws: AWS, region: Region, account: Account, function_name: str):
        super().__init__(aws, region, account)
        self.function_name = function_name
        logger.debug(f"new AWSLambdaFunction: {self.arn}")

    @property
    def arn(self) -> Arn:
        return Arn.AWSLambdaFunctionArn(self.region, self.account, self.function_name)

    @staticmethod
    def from_cfn(
        aws: AWS, region: Region, account: Account, cfn: Any
    ) -> AWSLambdaFunction:
        raise NotImplementedError


class AWSSQSQueue(Resource):
    def __init__(self, aws: AWS, region: Region, account: Account, queue_name: str):
        super().__init__(aws, region, account)
        self.queue_name = queue_name
        logger.debug(f"new AWSSQSQueue: {self.arn}")

    @property
    def arn(self) -> Arn:
        return Arn.AWSSQSQueueArn(self.region, self.account, self.queue_name)

    @staticmethod
    def from_cfn(aws: AWS, region: Region, account: Account, cfn: Any) -> AWSSQSQueue:
        raise NotImplementedError


##### CloudFormation
class CloudFormationTemplateError(Exception):
    pass


class CloudFormationStack:
    """A CloudFormation Stack, usually instantiated from a CloudFormation template file."""

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
        self._init_dependency_graph()
        # instantiate the resources in order, and register them at aws
        resources = self.template["Resources"]
        self.created_resources = [
            self.create_resource(resources[r])
            for r in self.logical_ids_by_dependency_order
        ]

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
        except nx.NetworkXUnfeasible:
            raise CloudFormationTemplateError(
                f"CloudFormation template is cyclic: {self.path}"
            )

        logger.debug(
            f"CloudFormation template ({self.path}) dependency graph: {self.dependency_graph.edges}"
        )

        logger.debug(
            f"CloudFormation template ({self.path}) dependency order: {self.logical_ids_by_dependency_order}"
        )

    def create_resource(self, body: CfnValue) -> Resource:
        rtype = body["Type"]
        assert isinstance(rtype, str)
        match rtype:
            case ResourceTypes.AWS_Lambda_Function:
                return self.aws.new_lambda_function(
                    self.region,
                    self.account,
                    body["Properties"]["FunctionName"],
                )
            case ResourceTypes.AWS_Serverless_Function:
                return self.aws.new_lambda_function(
                    self.region,
                    self.account,
                    body["Properties"]["FunctionName"],
                )
            case ResourceTypes.AWS_SQS_Queue:
                prop = body["Properties"]
                return self.aws.new_sqs_queue(
                    self.region,
                    self.account,
                    prop["QueueName"],
                )
            case _:
                raise UnknownResourceError(f"{rtype}")

    @classmethod
    def from_file(
        cls, aws: AWS, region: Region, account: Account, path: str | os.PathLike[Any]
    ):
        with open(path, "r") as f:
            try:
                data = cfn_flip.load_yaml(f)  # type: ignore
                logger.info(f"Loaded {path} as CloudFormation template in YAML format")
            except:
                try:
                    data = cfn_flip.load_json(f)  # type: ignore
                    logger.info(
                        f"Loaded {path} as a CloudFormation template in JSON format"
                    )
                except:
                    raise CloudFormationTemplateError(
                        f"Unable to load {path} as a CloudFormation template"
                    )

        return cls(aws, region, account, data, path)
