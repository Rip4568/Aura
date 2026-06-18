"""Tests for CompressionMiddleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from aura.middleware.compression import CompressionMiddleware


class TestCompressionMiddleware:
    """Tests for CompressionMiddleware."""

    def test_gzip_level_valid_range(self) -> None:
        """Test that gzip_level 1-9 is accepted."""
        for level in range(1, 10):
            middleware = CompressionMiddleware(gzip_level=level)
            assert middleware.gzip_level == level

    def test_gzip_level_default(self) -> None:
        """Test default gzip_level is 6."""
        middleware = CompressionMiddleware()
        assert middleware.gzip_level == 6

    @pytest.mark.parametrize("invalid_level", [0, 10, -1, 100])
    def test_gzip_level_invalid_raises(self, invalid_level: int) -> None:
        """Test that invalid gzip_level raises ValueError."""
        with pytest.raises(ValueError, match="gzip_level must be between 1 and 9"):
            CompressionMiddleware(gzip_level=invalid_level)

    def test_brotli_quality_default(self) -> None:
        """Test default brotli_quality is 4."""
        middleware = CompressionMiddleware()
        assert middleware.brotli_quality == 4

    @pytest.mark.parametrize("invalid_quality", [-1, 12, 100])
    def test_brotli_quality_invalid_raises(self, invalid_quality: int) -> None:
        with pytest.raises(ValueError, match="brotli_quality must be between 0 and 11"):
            CompressionMiddleware(brotli_quality=invalid_quality)

    def test_build_passes_compresslevel_to_gzip_middleware(self) -> None:
        """Test that build() passes compresslevel to GZipMiddleware."""
        app = MagicMock()
        middleware = CompressionMiddleware(minimum_size=512, gzip_level=3)

        with patch(
            "aura.middleware.compression.brotli",
            create=True,
            side_effect=ImportError,
        ), patch("starlette.middleware.gzip.GZipMiddleware") as mock_gzip:
            mock_gzip.return_value = MagicMock()
            middleware.build(app)

            mock_gzip.assert_called_once_with(
                app,
                minimum_size=512,
                compresslevel=3,
            )

    def test_build_uses_brotli_when_available(self) -> None:
        """Test that BrotliMiddleware is preferred when brotli is installed."""
        app = MagicMock()
        middleware = CompressionMiddleware(minimum_size=256, gzip_level=7, brotli_quality=7)

        mock_brotli_middleware = MagicMock()
        with patch.dict(
            "sys.modules",
            {
                "brotli": MagicMock(),
                "starlette_brotli": MagicMock(
                    BrotliMiddleware=mock_brotli_middleware
                ),
            },
        ):
            middleware.build(app)

            mock_brotli_middleware.assert_called_once_with(
                app,
                minimum_size=256,
                quality=7,
            )

    def test_call_alias_for_build(self) -> None:
        """Test that __call__ delegates to build."""
        app = MagicMock()
        middleware = CompressionMiddleware()

        with patch.object(middleware, "build", return_value=app) as mock_build:
            result = middleware(app)

            mock_build.assert_called_once_with(app)
            assert result is app
