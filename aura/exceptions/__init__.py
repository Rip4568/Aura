"""Exceptions module — HTTP exceptions and global error handlers."""

from aura.exceptions.base import AuraException
from aura.exceptions.http import (
    HTTPException,
    BadRequestException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ConflictException,
    UnprocessableEntityException,
    InternalServerException,
    ServiceUnavailableException,
    GatewayTimeoutException,
)
from aura.exceptions.handlers import exception_handler, validation_exception_handler

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
