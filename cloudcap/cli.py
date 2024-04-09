import sys
from typing import Optional
from typing_extensions import Annotated
import logging
import typer
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

app = typer.Typer()


def version_callback(value: bool) -> None:
    if value:
        print(f"{__app_name__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show the version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
    debug: Annotated[
        Optional[bool],
        typer.Option(
            "--debug",
            "-d",
            help="Enable debug mode for more detailed tracing.",
        ),
    ] = None,
) -> None:
    """
    IaC analysis tool.
    """
    logging_level = logging.WARNING
    if debug:
        logging_level = logging.DEBUG
    setup_logging(logging_level)


@app.command()
def analyze(
    cfn_template: Annotated[str, typer.Argument(help="CloudFormation template")],
    estimates_file: Annotated[str, typer.Argument(help="Estimates file")],
):
    """
    Check whether the usage estimates satisfy the constraints of the infrastructure.
    """

    # simulate AWS deployments
    aws = AWS()
    deployment = aws.add_deployment(Regions.us_east_1, Account("123"))
    deployment.from_cloudformation_template(path=cfn_template)

    # setup analysis
    analyzer = Analyzer(aws)
    analyzer.constrain()

    # add user estimates
    user_estimates = estimates.load(estimates_file)
    analyzer.add_estimates(user_estimates)

    # perform analysis
    result = analyzer.solve()

    # interpret analysis result
    if result == AnalyzerResult.PASS:
        print("✅ Pass")
        sys.exit(SUCCESS)
    elif result == AnalyzerResult.REJECT:
        print("❌ Reject")
        sys.exit(SOLVER_REJECT)
    else:
        print("⚠️ The solver failed to solve the constraints")
        sys.exit(SOLVER_ERROR)


@app.command()
def smt2(
    cfn_template: Annotated[str, typer.Argument(help="CloudFormation template")],
    estimates_file: Annotated[
        Optional[str], typer.Argument(help="Estimates file")
    ] = None,
):
    """
    Check whether the usage estimates satisfy the constraints of the infrastructure.
    """
    # simulate AWS deployments
    aws = AWS()
    deployment = aws.add_deployment(Regions.us_east_1, Account("123"))
    deployment.from_cloudformation_template(path=cfn_template)

    # setup analysis
    analyzer = Analyzer(aws)
    analyzer.constrain()

    # add user estimates
    if estimates_file:
        user_estimates = estimates.load(estimates_file)
        analyzer.add_estimates(user_estimates)

    # write smt2 to stdout
    print(analyzer.sexpr())
    sys.exit(SUCCESS)


@app.command()
def estimates_template(
    cfn_template: Annotated[str, typer.Argument(help="CloudFormation template")],
):
    """
    Generate a template estimates file file for the given CloudFormation template.
    """
    aws = AWS()
    deployment = aws.add_deployment(Regions.us_east_1, Account("123"))
    deployment.from_cloudformation_template(path=cfn_template)
    estimates.write_template(aws)
    sys.exit(SUCCESS)
