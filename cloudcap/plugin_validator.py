from cloudcap.plugins import Plugin
from cloudcap.aws import (
    AWSLambdaFunction, AWSLambdaAlias, LambdaEventSourceMapping,
    AWSSQSQueue, AWSSNSTopic, AWSSNSSubscription,
    AWSDynamoDBTable, AWSS3Bucket,
    AWSAPIGatewayRestApi, AWSAPIGatewayResource, AWSAPIGatewayMethod,
    AWSKinesisStream, AWSStepFunctionsStateMachine,
)
from cloudcap.metrics import (
    NREQUESTS, DYNAMODB_READ, DYNAMODB_WRITE, S3_GET, S3_PUT, HTTP_METHODS
)


_SCOPE = {
    "Plugin": Plugin,
    "AWSLambdaFunction": AWSLambdaFunction,
    "AWSLambdaAlias": AWSLambdaAlias,
    "LambdaEventSourceMapping": LambdaEventSourceMapping,
    "AWSSQSQueue": AWSSQSQueue,
    "AWSSNSTopic": AWSSNSTopic,
    "AWSSNSSubscription": AWSSNSSubscription,
    "AWSDynamoDBTable": AWSDynamoDBTable,
    "AWSS3Bucket": AWSS3Bucket,
    "AWSAPIGatewayRestApi": AWSAPIGatewayRestApi,
    "AWSAPIGatewayResource": AWSAPIGatewayResource,
    "AWSAPIGatewayMethod": AWSAPIGatewayMethod,
    "AWSKinesisStream": AWSKinesisStream,
    "AWSStepFunctionsStateMachine": AWSStepFunctionsStateMachine,
    "NREQUESTS": NREQUESTS,
    "DYNAMODB_READ": DYNAMODB_READ,
    "DYNAMODB_WRITE": DYNAMODB_WRITE,
    "S3_GET": S3_GET,
    "S3_PUT": S3_PUT,
    "HTTP_METHODS": HTTP_METHODS,
}


def load(code: str) -> type[Plugin]:
    namespace = dict(_SCOPE)
    try:
        exec(compile(code, "<generated>", "exec"), namespace)
    except NameError as e:
        raise ValueError(
            f"Generated code references an unknown name: {e}. "
            "The resource type may not have a corresponding class in aws.py."
        ) from e

    plugin_classes = [
        v for v in namespace.values()
        if isinstance(v, type) and issubclass(v, Plugin) and v is not Plugin
    ]

    if not plugin_classes:
        raise ValueError("No Plugin subclass found in generated code")
    if len(plugin_classes) > 1:
        raise ValueError(f"Expected 1 Plugin subclass, got {len(plugin_classes)}")

    cls = plugin_classes[0]

    if not callable(getattr(cls, "name", None)):
        raise ValueError(f"{cls.__name__} missing name() method")
    if not callable(getattr(cls, "constrain", None)):
        raise ValueError(f"{cls.__name__} missing constrain() method")

    return cls
