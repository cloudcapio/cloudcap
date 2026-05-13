import pytest
from cloudcap.aws import AWS, Regions, Account
from cloudcap import estimates
from cloudcap.analyzer import Analyzer, AnalyzerResult
from cloudcap.metrics import NREQUESTS


def make_analyzer(template_path: str) -> tuple[Analyzer, AWS]:
    aws = AWS()
    deployment = aws.add_deployment(Regions.us_east_1, Account("123"))
    deployment.from_cloudformation_template(path=template_path)
    analyzer = Analyzer(aws)
    analyzer.constrain()
    return analyzer, aws


class TestSqsLambda:
    TEMPLATE = "examples/sqs-lambda.yaml"

    def test_estimates_template_has_expected_resources(self):
        _, aws = make_analyzer(self.TEMPLATE)
        template = estimates.template_to_string(aws)
        assert "MyQueue" in template
        assert "LambdaFunction" in template
        assert NREQUESTS in template

    def test_pass_when_estimates_consistent(self):
        analyzer, _ = make_analyzer(self.TEMPLATE)
        analyzer.add_estimates(
            {"MyQueue": {NREQUESTS: 10}, "LambdaFunction": {NREQUESTS: 10}}
        )
        assert analyzer.solve() == AnalyzerResult.PASS

    def test_reject_when_queue_exceeds_lambda(self):
        analyzer, _ = make_analyzer(self.TEMPLATE)
        analyzer.add_estimates(
            {"MyQueue": {NREQUESTS: 999}, "LambdaFunction": {NREQUESTS: 10}}
        )
        assert analyzer.solve() == AnalyzerResult.REJECT

    def test_reject_when_lambda_exceeds_queue(self):
        analyzer, _ = make_analyzer(self.TEMPLATE)
        analyzer.add_estimates(
            {"MyQueue": {NREQUESTS: 10}, "LambdaFunction": {NREQUESTS: 999}}
        )
        assert analyzer.solve() == AnalyzerResult.REJECT

    def test_pass_with_zero_requests(self):
        analyzer, _ = make_analyzer(self.TEMPLATE)
        analyzer.add_estimates(
            {"MyQueue": {NREQUESTS: 0}, "LambdaFunction": {NREQUESTS: 0}}
        )
        assert analyzer.solve() == AnalyzerResult.PASS

    def test_smt2_output_is_non_empty(self):
        analyzer, _ = make_analyzer(self.TEMPLATE)
        smt2 = analyzer.sexpr()
        assert len(smt2) > 0
        assert "nrequests" in smt2
