import logging
import cfn_flip
import networkx as nx
import abc
import cloudcap.utils as utils

logger = logging.getLogger(__name__)


class UnknownArnError(Exception):
    pass


class AWS:
    def __init__(self):
        self.arns = dict()
        self.deployments = list()

    def add_deployment(self, *, region, account_id):
        d = Deployment(aws=self, region=region, account_id=account_id)
        self.deployments.append(d)
        return d

    def by_arn(self, arn):
        try:
            self.arns[arn]
        except KeyError as e:
            raise UnknownArnError(e.message)

    def new_lambda_function(self, *, region, account_id, function_name):
        r = AWSLambdaFunction(
            aws=self, region=region, account_id=account_id, function_name=function_name
        )
        self.register_resource(r)
        return r

    def new_sqs_queue(self, *, region, account_id, queue_name):
        r = AWSSQSQueue(
            aws=self, region=region, account_id=account_id, queue_name=queue_name
        )
        self.register_resource(r)
        return r

    def register_resource(self, r):
        if r.arn in self.arns:
            logger.warn(f"{r.arn} is already a registered resource")
        self.arns[r.arn] = r
        logger.info(f"registered resource {r.arn}")


class Deployment:
    def __init__(self, *, aws, region, account_id):
        logger.debug(f"new deployment ({region}, {account_id})")
        self.aws = aws
        self.region = region
        self.account_id = account_id

    def from_cloudformation_template(self, *, path: str):
        CloudFormationStack.from_file(
            aws=self.aws, region=self.region, account_id=self.account_id, path=path
        )


##### Regions and Partitions


class Region:
    def __init__(self, partition, region):
        self.partition = partition
        self.region = region

    def __str__(self):
        return self.region

    def __repr__(self):
        return str(self)


class Partitions:
    aws = "aws"


class Regions:
    us_east_1 = Region(Partitions.aws, "us-east-1")
    us_east_2 = Region(Partitions.aws, "us-east-2")


##### Arn


class Arn:
    @staticmethod
    def AWSLambdaFunctionArn(*, region, account_id, function_name):
        return f"arn:{region.partition}:lambda:{region}:{account_id}:function:{function_name}"

    @staticmethod
    def AWSSQSQueueArn(*, region, account_id, queue_name):
        return f"arn:{region.partition}:sqs:{region}:{account_id}:{queue_name}"


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
    def __init__(self, aws, region, account_id):
        self.aws = aws
        self.region = region
        self.account_id = account_id

    @abc.abstractproperty
    def arn(self):
        pass


class AWSLambdaFunction(Resource):
    def __init__(self, *, aws, region, account_id, function_name):
        super().__init__(aws, region, account_id)
        self.function_name = function_name
        logger.debug(f"new AWSLambdaFunction: {self.arn}")

    @property
    def arn(self):
        return Arn.AWSLambdaFunctionArn(
            region=self.region,
            account_id=self.account_id,
            function_name=self.function_name,
        )

    @staticmethod
    def from_cfn():
        raise NotImplementedError


class AWSSQSQueue(Resource):
    def __init__(self, *, aws, region, account_id, queue_name):
        super().__init__(aws, region, account_id)
        self.queue_name = queue_name
        logger.debug(f"new AWSSQSQueue: {self.arn}")

    @property
    def arn(self):
        return Arn.AWSSQSQueueArn(
            region=self.region, account_id=self.account_id, queue_name=self.queue_name
        )

    @staticmethod
    def from_cfn(*, aws, region, account_id, cfn):
        raise NotImplementedError


##### CloudFormation
class CloudFormationTemplateError(Exception):
    pass


class CloudFormationStack:
    """A CloudFormation Stack, usually instantiated from a CloudFormation template file."""

    def __init__(self, *, aws, region, account_id, template, path=""):
        self.aws = aws
        self.region = region
        self.account_id = account_id
        self.template = template
        self.path = path
        self._init_dependency_graph()
        # instantiate the resources in order, and register them at aws
        self.created_resources = [
            self.create_resource(self.template["Resources"][r])
            for r in self.logical_ids_by_dependency_order
        ]

    def _init_dependency_graph(self):
        self.dependency_graph = nx.DiGraph()
        resources = self.template["Resources"]
        for r in resources:
            self.dependency_graph.add_node(r)

        for r1 in resources:
            for r2, r2_body in resources.items():
                if utils.value_exists_in_nested_structure(r2_body, r1):
                    self.dependency_graph.add_edge(r1, r2)

        try:
            self.logical_ids_by_dependency_order = list(
                nx.topological_sort(self.dependency_graph)
            )
        except nx.NetworkXUnfeasible as e:
            raise CloudFormationTemplateError(
                f"CloudFormation template is cyclic: {self.path}"
            )

        logger.debug(
            f"CloudFormation template ({self.path}) dependency graph: {self.dependency_graph.edges}"
        )

        logger.debug(
            f"CloudFormation template ({self.path}) dependency order: {self.logical_ids_by_dependency_order}"
        )

    def create_resource(self, body):
        match body["Type"]:
            case ResourceTypes.AWS_Lambda_Function:
                return self.aws.new_lambda_function(
                    region=self.region,
                    account_id=self.account_id,
                    function_name=body["Properties"]["FunctionName"],
                )
            case ResourceTypes.AWS_Serverless_Function:
                return self.aws.new_lambda_function(
                    region=self.region,
                    account_id=self.account_id,
                    function_name=body["Properties"]["FunctionName"],
                )
            case ResourceTypes.AWS_SQS_Queue:
                prop = body["Properties"]
                return self.aws.new_sqs_queue(
                    region=self.region,
                    account_id=self.account_id,
                    queue_name=prop["QueueName"],
                )

    @classmethod
    def from_file(cls, *, aws, region, account_id, path: str):
        with open(path, "r") as f:
            try:
                data = cfn_flip.load_yaml(f)
                logger.info(f"Loaded {path} as CloudFormation template in YAML format")
            except:
                try:
                    data = cfn_flip.load_json(f)
                    logger.info(
                        f"Loaded {path} as a CloudFormation template in JSON format"
                    )
                except:
                    raise CloudFormationTemplateError(
                        f"Unable to load {path} as a CloudFormation template"
                    )

        return cls(
            aws=aws, region=region, account_id=account_id, template=data, path=path
        )
