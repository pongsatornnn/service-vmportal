"""Bound public record identifiers before they reach PostgreSQL integer columns."""

from typing import Annotated

from fastapi import Path

PortalID = Annotated[int, Path(ge=1, le=2_147_483_647)]
