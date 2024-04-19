# Cloudcap

## Prerequisites

1. [poetry](https://python-poetry.org/docs/)

## Getting started

To start, install the project dependencies:

```bash
make install
```

Enter the project's virtual environment:

```bash
make shell
```

Now you should have access to `cloudcap`:

```bash
cloudcap --help
```

## Deploy

should move this to the Makefile at some point

poetry run pip install --upgrade -t package dist/*.whl
cp deploy/lambda_function.py package
cd package ; zip -r ../artifact.zip . -x '*.pyc'

manually upload the zip to S3 (should also be part of the makefile using aws cli)
manually update the lambda from the uploaded zip (should also be part of the makefile using aws cli)

also

manually update the lambda source to be the s3 location of the zip (should be part of the clodformation file, once needs to happen once)

## Helpful documentations

1. [Development workflow with Poetry and Typer CLI](https://typer.tiangolo.com/tutorial/package/)
