from lambda_function import lambda_handler

payload = {
  "estimates": "MyQueue:\n  nrequests: 10\n\nLambdaFunction:\n  nrequests: 10",
  "cfn_template": "Resources:\n  LambdaFunction:\n    Type: AWS::Lambda::Function\n    Properties:\n      FunctionName: lambda1\n      Code:\n        S3Bucket: my-source-bucket\n        S3Key: lambda/my-nodejs-app.zip\n      Handler: index.handler\n      Runtime: nodejs8.10\n      Timeout: 60\n      MemorySize: 512\n      Environment:\n        TestQueue: !GetAtt MyQueue.Arn\n\n  LambdaFunctionEventSourceMapping:\n    Type: AWS::Lambda::EventSourceMapping\n    Properties:\n      BatchSize: 10\n      Enabled: true\n      EventSourceArn: !GetAtt MyQueue.Arn\n      FunctionName: !GetAtt LambdaFunction.Arn\n\n  MyQueue:\n    Type: AWS::SQS::Queue\n    Properties:\n      QueueName: queue1\n      DelaySeconds: 0\n      VisibilityTimeout: 120(cloudcap-py3.11) "
}

print(lambda_handler(payload, {}))