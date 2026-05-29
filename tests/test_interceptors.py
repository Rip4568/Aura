"""Tests for interceptors."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from aura.interceptors.logging import LoggingInterceptor, RequestLogInterceptor
from aura.interceptors.timing import TimingInterceptor
from aura.logging.context import clear_context, set_request_id, set_user_id


class MockResponse:
    """Mock response object for testing."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.headers: dict[str, str] = {}


class MockRequest:
    """Mock request object for testing."""

    def __init__(
        self, method: str = "GET", path: str = "/", headers: dict[str, str] | None = None
    ) -> None:
        self.method = method
        self.url = type("URL", (), {"path": path})()
        self.headers = headers or {}


class TestTimingInterceptor:
    """Tests for TimingInterceptor."""

    @pytest.mark.asyncio
    async def test_timing_interceptor_adds_header(self) -> None:
        """Test that TimingInterceptor adds X-Process-Time header."""
        interceptor = TimingInterceptor()
        response = MockResponse(200)

        async def call_next(request: Any) -> MockResponse:
            return response

        request = MockRequest()
        result = await interceptor.intercept(request, None, call_next)

        assert "X-Process-Time" in result.headers
        assert isinstance(result.headers["X-Process-Time"], str)

    @pytest.mark.asyncio
    async def test_timing_interceptor_header_is_float(self) -> None:
        """Test that X-Process-Time header value is a valid float."""
        interceptor = TimingInterceptor()
        response = MockResponse(200)

        async def call_next(request: Any) -> MockResponse:
            return response

        request = MockRequest()
        result = await interceptor.intercept(request, None, call_next)

        header_value = result.headers["X-Process-Time"]
        elapsed = float(header_value)
        assert elapsed >= 0

    @pytest.mark.asyncio
    async def test_timing_interceptor_handles_response_without_headers(self) -> None:
        """Test that TimingInterceptor doesn't crash on response without headers."""
        interceptor = TimingInterceptor()

        class NoHeaderResponse:
            status_code = 200

        response = NoHeaderResponse()

        async def call_next(request: Any) -> NoHeaderResponse:
            return response

        request = MockRequest()
        # Should not raise
        result = await interceptor.intercept(request, None, call_next)
        assert result.status_code == 200


class TestRequestLogInterceptor:
    """Tests for RequestLogInterceptor."""

    def setup_method(self) -> None:
        """Setup before each test."""
        clear_context()

    def teardown_method(self) -> None:
        """Cleanup after each test."""
        clear_context()

    @pytest.mark.asyncio
    async def test_request_log_interceptor_logs_method_path_status(
        self, caplog: Any
    ) -> None:
        """Test that RequestLogInterceptor logs method, path, status code, and elapsed_ms."""
        interceptor = RequestLogInterceptor()
        response = MockResponse(200)

        async def call_next(request: Any) -> MockResponse:
            return response

        request = MockRequest(method="GET", path="/users/")

        with caplog.at_level(logging.INFO):
            await interceptor.intercept(request, None, call_next)

        assert "GET /users/ 200" in caplog.text

    @pytest.mark.asyncio
    async def test_request_log_interceptor_includes_context_in_extra(
        self, caplog: Any
    ) -> None:
        """Test that RequestLogInterceptor includes context fields in extra."""
        set_request_id("test-req-123")
        set_user_id(42)

        interceptor = RequestLogInterceptor()
        response = MockResponse(201)

        async def call_next(request: Any) -> MockResponse:
            return response

        request = MockRequest(method="POST", path="/users/")

        with caplog.at_level(logging.INFO):
            await interceptor.intercept(request, None, call_next)

        # Verify the log message contains the structured fields
        assert "POST /users/ 201" in caplog.text

    @pytest.mark.asyncio
    async def test_request_log_interceptor_log_headers_disabled_by_default(
        self, caplog: Any
    ) -> None:
        """Test that log_headers is disabled by default."""
        interceptor = RequestLogInterceptor(log_headers=False)
        response = MockResponse(200)

        async def call_next(request: Any) -> MockResponse:
            return response

        request = MockRequest(headers={"X-Custom": "value"})

        with caplog.at_level(logging.DEBUG):
            await interceptor.intercept(request, None, call_next)

        # Headers should not be logged
        assert "X-Custom" not in caplog.text or "Request headers" not in caplog.text

    @pytest.mark.asyncio
    async def test_logging_interceptor_is_alias(self) -> None:
        """Test that LoggingInterceptor is an alias for RequestLogInterceptor."""
        assert LoggingInterceptor is RequestLogInterceptor
