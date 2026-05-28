"""Exceptions module — HTTP exceptions and global error handlers."""

from aura.exceptions.base import AuraException
from aura.exceptions.handlers import exception_handler, validation_exception_handler
from aura.exceptions.http import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    GatewayTimeoutException,
    HTTPException,
    InternalServerException,
    NotFoundException,
    ServiceUnavailableException,
    UnauthorizedException,
    UnprocessableEntityException,
)

__all__ = [
    "AuraException",
    "HTTPException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ConflictException",
    "UnprocessableEntityException",
    "InternalServerException",
    "ServiceUnavailableException",
    "GatewayTimeoutException",
    "exception_handler",
    "validation_exception_handler",
]
