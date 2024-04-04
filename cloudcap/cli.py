from typing import Optional
from typing_extensions import Annotated
import logging
import typer
from cloudcap import __app_name__, __version__
from cloudcap.aws import AWS, Regions
import cloudcap.cloudformation as cloudformation

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
    logging_level = logging.INFO
    if debug:
        logging_level = logging.DEBUG
    logging.basicConfig(level=logging_level)


@app.command()
def check(
    cfn_template: Annotated[str, typer.Argument(help="CloudFormation template")],
):
    """
    Check whether the usage estimates satisfy the constraints of the infrastructure.
    """
    aws = AWS()
    d = aws.add_deployment(region=Regions.us_east_1, account_id="123")
    d.from_cloudformation_template(cfn_template)
