# Cloudcap

## Prerequisites

1. [poetry](https://python-poetry.org/docs/)

## Getting started

To start, install the project dependencies:

```bash
make install
```

Enter the project's virtual environment:

```bash
make shell
```

Now you should have access to `cloudcap`:

```bash
cloudcap --help
```

## Deploy

should move this to the Makefile at some point

poetry run pip install --upgrade -t package dist/*.whl
cp deploy/lambda_function.py package
cd package && zip -r ../artifact.zip . -x '*.pyc'

manually upload the zip to S3 (should also be part of the makefile using aws cli)
manually update the lambda from the uploaded zip (should also be part of the makefile using aws cli)

also

manually update the lambda source to be the s3 location of the zip (should be part of the cloudformation file, once needs to happen once)

put this into Test for API Gateway:
{ "estimates": "MyQueue:\n  nrequests: 10\n\nLambdaFunction:\n  nrequests: 10",
  "cfn_template": "Resources:\n  LambdaFunction:\n    Type: AWS::Lambda::Function\n    Properties:\n      FunctionName: lambda1\n      Code:\n        S3Bucket: my-source-bucket\n        S3Key: lambda/my-nodejs-app.zip\n      Handler: index.handler\n      Runtime: nodejs8.10\n      Timeout: 60\n      MemorySize: 512\n      Environment:\n        TestQueue: !GetAtt MyQueue.Arn\n\n  LambdaFunctionEventSourceMapping:\n    Type: AWS::Lambda::EventSourceMapping\n    Properties:\n      BatchSize: 10\n      Enabled: true\n      EventSourceArn: !GetAtt MyQueue.Arn\n      FunctionName: !GetAtt LambdaFunction.Arn\n\n  MyQueue:\n    Type: AWS::SQS::Queue\n    Properties:\n      QueueName: queue1\n      DelaySeconds: 0\n      VisibilityTimeout: 120(cloudcap-py3.11) "
}

```
curl -X POST \
     -H "Content-Type: application/json" \
     -D - \
     -d '{ "estimates": "MyQueue:\n  nrequests: 10\n\nLambdaFunction:\n  nrequests: 10",  "cfn_template": "Resources:\n  LambdaFunction:\n    Type: AWS::Lambda::Function\n    Properties:\n      FunctionName: lambda1\n      Code:\n        S3Bucket: my-source-bucket\n        S3Key: lambda/my-nodejs-app.zip\n      Handler: index.handler\n      Runtime: nodejs8.10\n      Timeout: 60\n      MemorySize: 512\n      Environment:\n        TestQueue: !GetAtt MyQueue.Arn\n\n  LambdaFunctionEventSourceMapping:\n    Type: AWS::Lambda::EventSourceMapping\n    Properties:\n      BatchSize: 10\n      Enabled: true\n      EventSourceArn: !GetAtt MyQueue.Arn\n      FunctionName: !GetAtt LambdaFunction.Arn\n\n  MyQueue:\n    Type: AWS::SQS::Queue\n    Properties:\n      QueueName: queue1\n      DelaySeconds: 0\n      VisibilityTimeout: 120" }' \
     https://s99cj4ct84.execute-api.us-east-2.amazonaws.com/call
```

## Helpful documentations

1. [Development workflow with Poetry and Typer CLI](https://typer.tiangolo.com/tutorial/package/)
