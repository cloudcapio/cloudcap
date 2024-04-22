import os
import sys
from typing import Any, Optional, TextIO
from cloudcap.analyzer import NREQUESTS
from cloudcap.aws import AWS
import yaml
from io import StringIO

Estimates = dict[str, dict[str, int]]


def write_template(aws: AWS, path: Optional[str | os.PathLike[Any]] = None) -> None:
    # Get the YAML content as a string from _write_template
    content = template_to_string(aws)
    
    if path:
        # Write the content to a file if a path is provided
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        # Otherwise, print the content to standard output
        print(content)

def template_to_string(aws: AWS) -> str:
    # Create a StringIO object to temporarily hold the output
    temp_output = StringIO()
    
    for r in aws.arns.values():
        if r.logical_id:
            template = {f"{r.logical_id}": {"NREQUESTS": 0}}
            yaml.dump(template, temp_output)
            temp_output.write("\n")
    
    # Retrieve the string from StringIO and write it to the file
    template_string = temp_output.getvalue()
    temp_output.close()  # Close the StringIO object when done

    return template_string

def load(path: Optional[str | os.PathLike[Any]] = None) -> Estimates:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    else:
        return yaml.safe_load(sys.stdin)
