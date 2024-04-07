from typing import Any

CfnValue = Any


def exists_in_cfn_value(value: CfnValue, target: str) -> bool:
    """
    Check if a value exists in an arbitrarily nested dictionary that can have lists nested inside as well.

    Args:
    structure (dict or list): The nested dictionary or list to search in.
    value: The value to search for.

    Returns:
    bool: True if the value exists, False otherwise.
    """
    if isinstance(value, dict):
        # Check if the value exists in the dictionary
        if target in value.values():
            return True
        # Recursively search in each value of the dictionary
        v: Any
        for v in value.values():
            if exists_in_cfn_value(v, target):
                return True
    elif isinstance(value, list):
        # Recursively search in each element of the list
        item: Any
        for item in value:
            if item == target:
                return True
            if exists_in_cfn_value(item, target):
                return True
    # If the value is not found in the current level, return False
    return False
