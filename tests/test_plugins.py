"""
Integration tests for cloudcap built-in plugins.

Tests verify constraint generation and satisfiability (PASS/REJECT) for each
supported AWS resource type. Estimates use lowercase metric keys matching the
constants in cloudcap.metrics (e.g. "nrequests", not "NREQUESTS").
"""
import os
import tempfile
import textwrap
import unittest

from cloudcap.analyzer import Analyzer, AnalyzerResult
from cloudcap.aws import (
    AWS,
    Account,
    AWSAPIGatewayMethod,
    AWSAPIGatewayRestApi,
    AWSLambdaAlias,
    AWSLambdaFunction,
    AWSSNSTopic,
    AWSSQSQueue,
    LambdaEventSourceMapping,
    Regions,
)
from cloudcap.metrics import (
    DYNAMODB_READ,
    DYNAMODB_WRITE,
    NREQUESTS,
    S3_GET,
    S3_PUT,
)

REGION = Regions.us_east_1
ACCOUNT = Account("123")


def _aws_from_yaml(yaml_str: str) -> AWS:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        f.write(textwrap.dedent(yaml_str))
        path = f.name
    try:
        aws = AWS()
        aws.add_deployment(REGION, ACCOUNT).from_cloudformation_template(path=path)
    finally:
        os.unlink(path)
    return aws


def _solve(aws: AWS, estimates: dict) -> AnalyzerResult:
    analyzer = Analyzer(aws)
    analyzer.constrain()
    analyzer.add_estimates(estimates)
    return analyzer.solve()


PASS = AnalyzerResult.PASS
REJECT = AnalyzerResult.REJECT


# ---------------------------------------------------------------------------
# SQS → EventSourceMapping → Lambda
# ---------------------------------------------------------------------------

SQS_LAMBDA_YAML = """\
Resources:
  Queue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: myqueue

  Mapping:
    Type: AWS::Lambda::EventSourceMapping
    Properties:
      EventSourceArn: arn:aws:sqs:us-east-1:123:myqueue
      FunctionName: myfn

  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"
"""


class TestSQSLambdaChain(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(SQS_LAMBDA_YAML)

    def test_resources_parsed(self):
        self.assertIn("Queue", self.aws.logical_id_to_resource)
        self.assertIn("Mapping", self.aws.logical_id_to_resource)
        self.assertIn("Fn", self.aws.logical_id_to_resource)
        self.assertIsInstance(self.aws.logical_id_to_resource["Queue"], AWSSQSQueue)
        self.assertIsInstance(
            self.aws.logical_id_to_resource["Mapping"], LambdaEventSourceMapping
        )
        self.assertIsInstance(self.aws.logical_id_to_resource["Fn"], AWSLambdaFunction)

    def test_consistent_estimates_pass(self):
        # queue == mapping == lambda: all equal, constraint chain satisfied
        result = _solve(
            self.aws,
            {
                "Queue": {NREQUESTS: 100},
                "Mapping": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_lambda_less_than_queue_rejects(self):
        # lambda must equal queue through the chain: queue→mapping→lambda
        result = _solve(
            self.aws,
            {
                "Queue": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 50},
            },
        )
        self.assertEqual(result, REJECT)

    def test_lambda_greater_than_queue_rejects(self):
        result = _solve(
            self.aws,
            {
                "Queue": {NREQUESTS: 50},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, REJECT)

    def test_zero_requests_passes(self):
        result = _solve(
            self.aws,
            {
                "Queue": {NREQUESTS: 0},
                "Mapping": {NREQUESTS: 0},
                "Fn": {NREQUESTS: 0},
            },
        )
        self.assertEqual(result, PASS)


# ---------------------------------------------------------------------------
# SQS FIFO with content-based deduplication
# ---------------------------------------------------------------------------

SQS_FIFO_LAMBDA_YAML = """\
Resources:
  Queue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: myqueue.fifo
      FifoQueue: true
      ContentBasedDeduplication: true

  Mapping:
    Type: AWS::Lambda::EventSourceMapping
    Properties:
      EventSourceArn: arn:aws:sqs:us-east-1:123:myqueue.fifo
      FunctionName: myfn

  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"
"""


class TestSQSFIFODeduplication(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(SQS_FIFO_LAMBDA_YAML)

    def test_queue_deduplicates(self):
        queue = self.aws.logical_id_to_resource["Queue"]
        self.assertIsInstance(queue, AWSSQSQueue)
        self.assertTrue(queue.deduplicates)

    def test_fewer_deliveries_than_arrivals_passes(self):
        # Dedup may drop messages: mapping can deliver fewer than queue received
        result = _solve(
            self.aws,
            {
                "Queue": {NREQUESTS: 100},
                "Mapping": {NREQUESTS: 60},
            },
        )
        self.assertEqual(result, PASS)

    def test_more_deliveries_than_arrivals_rejects(self):
        # Mapping can never deliver more than what arrived at the queue
        result = _solve(
            self.aws,
            {
                "Queue": {NREQUESTS: 50},
                "Mapping": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, REJECT)


# ---------------------------------------------------------------------------
# SNS topic → Lambda (inline subscription)
# ---------------------------------------------------------------------------

SNS_LAMBDA_YAML = """\
Resources:
  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"

  Topic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: mytopic
      Subscription:
        - Endpoint: !GetAtt Fn.Arn
          Protocol: lambda
"""


class TestSNSTopic(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(SNS_LAMBDA_YAML)

    def test_resources_parsed(self):
        self.assertIn("Topic", self.aws.logical_id_to_resource)
        self.assertIsInstance(self.aws.logical_id_to_resource["Topic"], AWSSNSTopic)

    def test_consistent_estimates_pass(self):
        # Every SNS message reaches the subscriber (fan-out = 1 here)
        result = _solve(
            self.aws,
            {
                "Topic": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_lambda_less_than_topic_rejects(self):
        result = _solve(
            self.aws,
            {
                "Topic": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 50},
            },
        )
        self.assertEqual(result, REJECT)

    def test_lambda_greater_than_topic_rejects(self):
        result = _solve(
            self.aws,
            {
                "Topic": {NREQUESTS: 50},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, REJECT)


# ---------------------------------------------------------------------------
# SNS Subscription (standalone resource)
# ---------------------------------------------------------------------------

SNS_SUBSCRIPTION_YAML = """\
Resources:
  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"

  Topic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: mytopic

  Sub:
    Type: AWS::SNS::Subscription
    Properties:
      TopicArn: !Ref Topic
      Protocol: lambda
      Endpoint: !GetAtt Fn.Arn
"""


class TestSNSSubscription(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(SNS_SUBSCRIPTION_YAML)

    def test_consistent_estimates_pass(self):
        result = _solve(
            self.aws,
            {
                "Topic": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_inconsistent_estimates_reject(self):
        result = _solve(
            self.aws,
            {
                "Topic": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 50},
            },
        )
        self.assertEqual(result, REJECT)


# ---------------------------------------------------------------------------
# Lambda Alias (transparent proxy)
# ---------------------------------------------------------------------------

LAMBDA_ALIAS_YAML = """\
Resources:
  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"

  Alias:
    Type: AWS::Lambda::Alias
    Properties:
      FunctionName: !Ref Fn
      FunctionVersion: '$LATEST'
      Name: live
"""


class TestLambdaAlias(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(LAMBDA_ALIAS_YAML)

    def test_resources_parsed(self):
        self.assertIn("Alias", self.aws.logical_id_to_resource)
        self.assertIsInstance(
            self.aws.logical_id_to_resource["Alias"], AWSLambdaAlias
        )

    def test_equal_requests_pass(self):
        # Alias is a transparent proxy: alias.NREQUESTS == function.NREQUESTS
        result = _solve(
            self.aws,
            {
                "Alias": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_alias_more_than_function_rejects(self):
        result = _solve(
            self.aws,
            {
                "Alias": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 50},
            },
        )
        self.assertEqual(result, REJECT)

    def test_alias_less_than_function_rejects(self):
        result = _solve(
            self.aws,
            {
                "Alias": {NREQUESTS: 50},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, REJECT)


# ---------------------------------------------------------------------------
# DynamoDB (passive sink with separate read/write metrics)
# ---------------------------------------------------------------------------

LAMBDA_DYNAMODB_YAML = """\
Resources:
  Table:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: mytable
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"
      Environment:
        TABLE_ARN: arn:aws:dynamodb:us-east-1:123:table/mytable
"""


class TestDynamoDBTable(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(LAMBDA_DYNAMODB_YAML)

    def test_resources_parsed(self):
        self.assertIn("Table", self.aws.logical_id_to_resource)

    def test_read_write_variables_created(self):
        aws = self.aws
        analyzer = Analyzer(aws)
        analyzer.constrain()
        table = aws.logical_id_to_resource["Table"]
        node_metrics = {metric for (_, metric) in analyzer.node_variables}
        self.assertIn(DYNAMODB_READ, node_metrics)
        self.assertIn(DYNAMODB_WRITE, node_metrics)

    def test_consistent_read_write_estimates_pass(self):
        result = _solve(
            self.aws,
            {
                "Table": {DYNAMODB_READ: 200, DYNAMODB_WRITE: 50},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_negative_read_rejects(self):
        result = _solve(
            self.aws,
            {"Table": {DYNAMODB_READ: -1}},
        )
        self.assertEqual(result, REJECT)


# ---------------------------------------------------------------------------
# S3 (passive sink with GET/PUT metrics)
# ---------------------------------------------------------------------------

LAMBDA_S3_YAML = """\
Resources:
  Bucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: mybucket

  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"
      Environment:
        BUCKET_ARN: arn:aws:s3:::mybucket
"""


class TestS3Bucket(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(LAMBDA_S3_YAML)

    def test_resources_parsed(self):
        self.assertIn("Bucket", self.aws.logical_id_to_resource)

    def test_get_put_variables_created(self):
        analyzer = Analyzer(self.aws)
        analyzer.constrain()
        node_metrics = {metric for (_, metric) in analyzer.node_variables}
        self.assertIn(S3_GET, node_metrics)
        self.assertIn(S3_PUT, node_metrics)

    def test_consistent_estimates_pass(self):
        result = _solve(
            self.aws,
            {"Bucket": {S3_GET: 500, S3_PUT: 100}},
        )
        self.assertEqual(result, PASS)

    def test_negative_put_rejects(self):
        result = _solve(
            self.aws,
            {"Bucket": {S3_PUT: -1}},
        )
        self.assertEqual(result, REJECT)


# ---------------------------------------------------------------------------
# API Gateway: RestApi → Method → Lambda
# ---------------------------------------------------------------------------

APIGW_LAMBDA_YAML = """\
Resources:
  Api:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: myapi

  Fn:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: myfn
      Handler: index.handler
      Runtime: nodejs18.x
      Code:
        ZipFile: "exports.handler = async (e) => {}"

  GetMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref Api
      ResourceId: !GetAtt Api.RootResourceId
      HttpMethod: GET
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        Uri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123:function:myfn/invocations
"""


class TestAPIGatewayMethod(unittest.TestCase):
    def setUp(self):
        self.aws = _aws_from_yaml(APIGW_LAMBDA_YAML)

    def test_resources_parsed(self):
        self.assertIn("Api", self.aws.logical_id_to_resource)
        self.assertIn("GetMethod", self.aws.logical_id_to_resource)
        self.assertIsInstance(
            self.aws.logical_id_to_resource["Api"], AWSAPIGatewayRestApi
        )
        self.assertIsInstance(
            self.aws.logical_id_to_resource["GetMethod"], AWSAPIGatewayMethod
        )

    def test_method_routes_to_lambda(self):
        # method.NREQUESTS == lambda.NREQUESTS (via outgoing + incoming constraints)
        result = _solve(
            self.aws,
            {
                "GetMethod": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_method_lambda_mismatch_rejects(self):
        result = _solve(
            self.aws,
            {
                "GetMethod": {NREQUESTS: 100},
                "Fn": {NREQUESTS: 50},
            },
        )
        self.assertEqual(result, REJECT)

    def test_method_intrinsic_get_equals_nrequests(self):
        # For a GET-only method: method.NREQUESTS == method.GET
        result = _solve(
            self.aws,
            {
                "GetMethod": {NREQUESTS: 100, "GET": 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_method_intrinsic_get_mismatch_rejects(self):
        result = _solve(
            self.aws,
            {
                "GetMethod": {NREQUESTS: 100, "GET": 50},
            },
        )
        self.assertEqual(result, REJECT)


# ---------------------------------------------------------------------------
# Example files (regression tests)
# ---------------------------------------------------------------------------

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")


class TestExampleTemplates(unittest.TestCase):
    def _aws_from_example(self, filename: str) -> AWS:
        path = os.path.join(EXAMPLES_DIR, filename)
        aws = AWS()
        aws.add_deployment(REGION, ACCOUNT).from_cloudformation_template(path=path)
        return aws

    def test_sqs_lambda_parses(self):
        aws = self._aws_from_example("sqs-lambda.yaml")
        self.assertIn("LambdaFunction", aws.logical_id_to_resource)
        self.assertIn("MyQueue", aws.logical_id_to_resource)
        self.assertIn("LambdaFunctionEventSourceMapping", aws.logical_id_to_resource)

    def test_sqs_lambda_consistent_pass(self):
        aws = self._aws_from_example("sqs-lambda.yaml")
        result = _solve(
            aws,
            {
                "MyQueue": {NREQUESTS: 100},
                "LambdaFunctionEventSourceMapping": {NREQUESTS: 100},
                "LambdaFunction": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_sqs_lambda_inconsistent_rejects(self):
        aws = self._aws_from_example("sqs-lambda.yaml")
        result = _solve(
            aws,
            {
                "MyQueue": {NREQUESTS: 100},
                "LambdaFunction": {NREQUESTS: 50},
            },
        )
        self.assertEqual(result, REJECT)

    def test_sns_lambda_alias_parses(self):
        aws = self._aws_from_example("sns-lambda-alias.yaml")
        self.assertIn("AwsServerlessExpressFunction", aws.logical_id_to_resource)
        self.assertIn("AwsServerlessExpressFunctionAlias", aws.logical_id_to_resource)
        self.assertIn("SNSTopic", aws.logical_id_to_resource)

    def test_sns_lambda_alias_consistent_pass(self):
        aws = self._aws_from_example("sns-lambda-alias.yaml")
        result = _solve(
            aws,
            {
                "SNSTopic": {NREQUESTS: 100},
                "AwsServerlessExpressFunctionAlias": {NREQUESTS: 100},
                "AwsServerlessExpressFunction": {NREQUESTS: 100},
            },
        )
        self.assertEqual(result, PASS)

    def test_sns_lambda_alias_inconsistent_rejects(self):
        aws = self._aws_from_example("sns-lambda-alias.yaml")
        result = _solve(
            aws,
            {
                "SNSTopic": {NREQUESTS: 100},
                "AwsServerlessExpressFunction": {NREQUESTS: 50},
            },
        )
        self.assertEqual(result, REJECT)


if __name__ == "__main__":
    unittest.main()
