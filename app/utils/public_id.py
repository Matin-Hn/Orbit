import random
import string

_ALPHABET = string.ascii_letters + string.digits  # a-z, A-Z, 0-9 = 62 chars
_PUBLIC_ID_LENGTH = 8
_MAX_RETRIES = 5


def generate_candidate() -> str:
    """Generate a random base62 string of 8 length."""
    return "".join(random.choices(_ALPHABET, k=_PUBLIC_ID_LENGTH))