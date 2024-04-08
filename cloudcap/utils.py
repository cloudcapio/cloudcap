import random
import string


def random_id() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=10))
