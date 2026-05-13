import os
from cloudcap.aws import (
    Resource, LambdaEventSource, LambdaEventSourceMapping,
    ArnBuilder, AWS, Account, Region, Regions, Partitions,
    AWSLambdaFunction, AWSLambdaAlias, AWSSQSQueue, AWSSNSTopic,
    AWSSNSSubscription, AWSDynamoDBTable, AWSS3Bucket,
    AWSAPIGatewayRestApi, AWSAPIGatewayResource, AWSAPIGatewayMethod,
    AWSKinesisStream, AWSStepFunctionsStateMachine,
)
from typing import Optional, cast
import abc

CACHE_DIR = os.path.join(os.path.dirname(__file__), "aws_generated")

_SCOPE = {
    "Resource": Resource,
    "LambdaEventSource": LambdaEventSource,
    "LambdaEventSourceMapping": LambdaEventSourceMapping,
    "ArnBuilder": ArnBuilder,
    "AWS": AWS,
    "Account": Account,
    "Region": Region,
    "Regions": Regions,
    "Partitions": Partitions,
    "AWSLambdaFunction": AWSLambdaFunction,
    "AWSLambdaAlias": AWSLambdaAlias,
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
    "Optional": Optional,
    "cast": cast,
    "abc": abc,
}


def _type_to_filename(resource_type: str) -> str:
    return resource_type.replace("::", "_").replace(" ", "") + ".py"


def save(resource_type: str, code: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, _type_to_filename(resource_type))
    with open(path, "w") as f:
        f.write(f"# Generated resource class for {resource_type}\n")
        f.write(code)
    return path


def is_cached(resource_type: str) -> bool:
    return os.path.exists(os.path.join(CACHE_DIR, _type_to_filename(resource_type)))


def load_all() -> list[type[Resource]]:
    if not os.path.exists(CACHE_DIR):
        return []
    classes = []
    for filename in os.listdir(CACHE_DIR):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(CACHE_DIR, filename)
        with open(path, "r") as f:
            code = f.read()
        try:
            namespace = dict(_SCOPE)
            exec(compile(code, path, "exec"), namespace)
            for obj in namespace.values():
                if isinstance(obj, type) and issubclass(obj, Resource) and obj is not Resource and hasattr(obj, "cfn_type"):
                    classes.append(obj)
        except Exception as e:
            print(f"Warning: failed to load cached resource class {filename}: {e}")
    return classes
