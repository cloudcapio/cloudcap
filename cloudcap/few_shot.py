import inspect
from cloudcap.cfn_schema import fetch, summarize
from cloudcap.plugins.builtin_plugins import (
    AWSSNSTopicPlugin,
    AWSDynamoDBTablePlugin,
    AWSLambdaAliasPlugin,
    AWSAPIGatewayMethodPlugin,
)

EXAMPLES = [
    ("AWS::SNS::Topic", AWSSNSTopicPlugin),
    ("AWS::DynamoDB::Table", AWSDynamoDBTablePlugin),
    ("AWS::Lambda::Alias", AWSLambdaAliasPlugin),
    ("AWS::ApiGateway::Method", AWSAPIGatewayMethodPlugin),
]


def get_examples() -> list[dict]:
    result = []
    for resource_type, plugin_class in EXAMPLES:
        schema = summarize(fetch(resource_type))
        code = inspect.getsource(plugin_class)
        result.append({
            "resource_type": resource_type,
            "schema": schema,
            "plugin_code": code,
        })
    return result
