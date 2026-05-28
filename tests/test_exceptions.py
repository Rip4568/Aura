"""Tests for aura.exceptions module."""

from __future__ import annotations

from aura.exceptions.base import AuraException
from aura.exceptions.http import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    HTTPException,
    InternalServerException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableEntityException,
)


def test_aura_exception_basic() -> None:
    exc = AuraException("Something went wrong")
    assert str(exc) == "Something went wrong"
    assert exc.message == "Something went wrong"
    assert exc.code is None
    assert exc.detail is None


def test_aura_exception_with_code_and_detail() -> None:
    exc = AuraException("Not found", code="NF001", detail={"id": 42})
    assert exc.code == "NF001"
    assert exc.detail == {"id": 42}


def test_http_exception_to_dict() -> None:
    exc = HTTPException(404, "Not Found", code="NOT_FOUND")
    payload = exc.to_dict()
    assert payload["error"]["status"] == 404
    assert payload["error"]["message"] == "Not Found"
    assert payload["error"]["code"] == "NOT_FOUND"


def test_http_exception_to_dict_no_code() -> None:
    exc = HTTPException(500, "Server Error")
    payload = exc.to_dict()
    assert "code" not in payload["error"]


def test_bad_request_exception() -> None:
    exc = BadRequestException()
    assert exc.status_code == 400
    assert exc.code == "BAD_REQUEST"


def test_unauthorized_exception() -> None:
    exc = UnauthorizedException()
    assert exc.status_code == 401


def test_forbidden_exception() -> None:
    exc = ForbiddenException()
    assert exc.status_code == 403


def test_not_found_exception() -> None:
    exc = NotFoundException("User not found")
    assert exc.status_code == 404
    assert "not found" in exc.message.lower()


def test_conflict_exception() -> None:
    exc = ConflictException()
    assert exc.status_code == 409


def test_unprocessable_entity_exception() -> None:
    exc = UnprocessableEntityException()
    assert exc.status_code == 422


def test_internal_server_exception() -> None:
    exc = InternalServerException()
    assert exc.status_code == 500


def test_exception_inherits_aura_exception() -> None:
    exc = NotFoundException()
    assert isinstance(exc, AuraException)
    assert isinstance(exc, HTTPException)


def test_exception_with_headers() -> None:
    exc = UnauthorizedException(headers={"WWW-Authenticate": "Bearer"})
    assert exc.headers["WWW-Authenticate"] == "Bearer"
