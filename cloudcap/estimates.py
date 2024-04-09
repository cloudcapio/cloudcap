import os
import sys
from typing import Any, Optional, TextIO
from cloudcap.analyzer import NREQUESTS
from cloudcap.aws import AWS
import yaml

Estimates = dict[str, dict[str, int]]


def write_template(aws: AWS, path: Optional[str | os.PathLike[Any]] = None) -> None:
    if path:
        with open(path, "w", encoding="utf-8") as f:
            _write_template(aws, f)
    else:
        _write_template(aws, sys.stdout)


def _write_template(aws: AWS, f: TextIO) -> None:
    for r in aws.arns.values():
        if r.logical_id:
            f.write(f"# {r.logical_id}\n")
        template = {f"{r.arn}": {NREQUESTS: 0}}
        yaml.dump(template, f)
        f.write("\n")


def load(path: Optional[str | os.PathLike[Any]] = None) -> Estimates:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    else:
        return yaml.safe_load(sys.stdin)
