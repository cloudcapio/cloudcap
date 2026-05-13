from cloudcap.aws import *


def test_AWSLambdaFunction_arn():
    aws = AWS()
    region = Regions.us_east_1
    account = Account("1234567890")
    function_name = "test_lambda"
    f = AWSLambdaFunction(
        aws=aws, region=region, account=account, function_name=function_name
    )
    assert f.arn == "arn:aws:lambda:us-east-1:1234567890:function:test_lambda"
