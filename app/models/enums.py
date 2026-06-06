"""Enum definitions used across the application."""

from enum import Enum


class MatchStatus(str, Enum):
    """Status of a job match from the user's perspective."""

    NEW = "new"
    APPLIED = "applied"
    NOT_INTERESTED = "not_interested"
    SAVED = "saved"
