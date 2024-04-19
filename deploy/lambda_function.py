from cloudcap import (
    SOLVER_ERROR,
    SOLVER_REJECT,
    SUCCESS,
    __app_name__,
    __version__,
    estimates,
)
from cloudcap.analyzer import Analyzer, AnalyzerResult
from cloudcap.aws import AWS, Regions, Account
from cloudcap.logging import setup_logging
import tempfile
import json

def lambda_handler(event, context):
    aws = AWS()
    deployment = aws.add_deployment(Regions.us_east_1, Account("123"))

    loadedBody = json.loads(event['body'])

    # Write CloudFormation template to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as cfn_file:
        cfn_file.write(loadedBody['cfn_template'])
        cfn_file_path = cfn_file.name
    deployment.from_cloudformation_template(path=cfn_file_path)

    # setup analysis
    analyzer = Analyzer(aws)
    analyzer.constrain()

    # Write user estimates to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as estimates_file:
        estimates_file.write(loadedBody['estimates'])
        estimates_file_path = estimates_file.name

    # add estimates    
    user_estimates = estimates.load(estimates_file_path)
    analyzer.add_estimates(user_estimates)

    # perform analysis
    result = analyzer.solve()

    api_response = ""

    if result == AnalyzerResult.PASS:
        api_response = "PASS"
    elif result == AnalyzerResult.REJECT:
        api_response = "REJECT"
    else:
        api_response = "ERROR"

    return {
        'statusCode': 200, 
        'body': json.dumps({'result' : api_response}),
        'headers': {
            "Access-Control-Allow-Origin": "*"
        },
    }
