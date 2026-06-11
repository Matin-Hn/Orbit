class ReactionNotFound(Exception):
    """Raised when no reaction exists for the given user/video pair."""
    pass


class ReactionTypeMismatch(Exception):
    """Raised when the requested reaction type doesn't match the existing one."""
    pass