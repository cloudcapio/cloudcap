# TODO need to update this so it is actually calling cloudcap - files are passed in as strings in the POST request?

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

def lambda_handler(event, context):

    aws = AWS()
    deployment = aws.add_deployment(Regions.us_east_1, Account("123"))
    deployment.from_cloudformation_template(path=event['cfn_template'])#TODO this isnt right....

    # setup analysis
    analyzer = Analyzer(aws)
    analyzer.constrain()

    # add user estimates
    user_estimates = estimates.load(event['estimates_file']) #TODO this isnt right...
    analyzer.add_estimates(user_estimates)

    # perform analysis
    result = analyzer.solve()
    return { 
        'result' : result
    }
