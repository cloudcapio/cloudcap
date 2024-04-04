import logging
import abc
from cloudcap.cloudformation import CloudFormationStack

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


class Deployment:
    def __init__(self, *, aws, region, account_id):
        logger.debug(f"new deployment ({region}, {account_id})")
        self.aws = aws
        self.region = region
        self.account_id = account_id

    def from_cloudformation_template(self, fpath):
        CloudFormationStack.from_file(fpath)


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


##### Resources


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


##### Arn


class Arn:
    @staticmethod
    def AWSLambdaFunctionArn(*, region, account_id, function_name):
        return f"arn:{region.partition}:lambda:{region}:{account_id}:function:{function_name}"

    @staticmethod
    def AWSSQSQueueArn(*, region, account_id, queue_name):
        return f"arn:{region.partition}:sqs:{region}:{account_id}:{queue_name}"
