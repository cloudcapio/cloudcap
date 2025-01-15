# Cloudcap

[![Python](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/badge/poetry-package%20manager-blue)](https://python-poetry.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> A tool for verifying the viability of AWS CloudFormation template cost estimates. If your cost estimates are not consistent with your cloud architecture, this tool will help you identify the discrepancies.

## Getting Started

### Prerequisites

- Python 3.7 or higher
- [Poetry](https://python-poetry.org/docs/) (Python package manager)

### Installation

1. Install project dependencies:
```bash
make install
```

2. Enter the project's virtual environment:
```bash
make shell
```

### Quick Start

Once installed, access the `cloudcap` CLI:
```bash
cloudcap --help
```

## Deployment

> **Note:** Automation of these steps is planned for future releases

### Manual Deployment Steps

1. Build and package the Lambda:
```bash
poetry run pip install --upgrade -t package dist/*.whl
cp deploy/lambda_function.py package
cd package && zip -r ../artifact.zip . -x '*.pyc'
```

2. AWS Deployment Steps:
   - Upload the zip to S3 (pending automation)
   - Update the Lambda from the uploaded zip (pending automation)
   - Update Lambda source in CloudFormation to point to S3 location (one-time setup)

## Testing

### API Gateway Testing

Use this JSON payload for API Gateway tests:

```json
{
    "estimates": "MyQueue:\n  nrequests: 10\n\nLambdaFunction:\n  nrequests: 10",
    "cfn_template": "Resources:\n  LambdaFunction:\n    Type: AWS::Lambda::Function\n    Properties:\n      FunctionName: lambda1\n      Code:\n        S3Bucket: my-source-bucket\n        S3Key: lambda/my-nodejs-app.zip\n      Handler: index.handler\n      Runtime: nodejs8.10\n      Timeout: 60\n      MemorySize: 512\n      Environment:\n        TestQueue: !GetAtt MyQueue.Arn\n\n  LambdaFunctionEventSourceMapping:\n    Type: AWS::Lambda::EventSourceMapping\n    Properties:\n      BatchSize: 10\n      Enabled: true\n      EventSourceArn: !GetAtt MyQueue.Arn\n      FunctionName: !GetAtt LambdaFunction.Arn\n\n  MyQueue:\n    Type: AWS::SQS::Queue\n    Properties:\n      QueueName: queue1\n      DelaySeconds: 0\n      VisibilityTimeout: 120"
}
```

#### API Testing with cURL

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -D - \
     -d '@payload.json' \
     https://s99cj4ct84.execute-api.us-east-2.amazonaws.com/call
```

## Documentation

- [Development workflow with Poetry and Typer CLI](https://typer.tiangolo.com/tutorial/package/)
- [API Documentation](docs/api.md)
- [Configuration Guide](docs/configuration.md)

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Submitting bug reports and feature requests
- Code contribution workflow
- Testing requirements
- Code review process

## Support

- [Open an issue](https://github.com/yourusername/cloudcap/issues)
- [Read the documentation](docs/)
- [Check examples](examples/)

## Cite

If you use this tool in your research, please cite:
- [Statically Inferring Usage Bounds for Infrastructure as Code](https://arxiv.org/abs/2402.15632), published at VSTTE 2024

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
