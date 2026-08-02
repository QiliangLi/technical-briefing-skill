from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)


class HttpRetryError(RuntimeError):
    def __init__(
        self,
        *,
        url: str,
        attempts: int,
        status_code: int | None = None,
        cause: Exception | None = None,
    ):
        context = f"status={status_code}" if status_code is not None else f"transport={type(cause).__name__}"
        super().__init__(f"HTTP request failed after {attempts} attempts: {context} url={url}")
        self.url = url
        self.attempts = attempts
        self.status_code = status_code
        self.cause = cause


def retry_after_seconds(value: str | None, *, fallback: float, now: datetime | None = None) -> float:
    if value:
        try:
            seconds = float(value.strip())
            if math.isfinite(seconds):
                return min(max(seconds, 0.0), 60.0)
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            current = now or datetime.now(timezone.utc)
            return min(max((retry_at - current).total_seconds(), 0.0), 60.0)
        except (IndexError, TypeError, ValueError, OverflowError):
            pass
    return min(max(float(fallback), 0.0), 60.0)


class HttpClient:
    def __init__(self, timeout: float = 25, user_agent: str = "TechnicalBriefingSkill/0.1"):
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": user_agent, "Accept": "*/*"},
        )

    def close(self) -> None:
        self.client.close()

    def get(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None, retries: int = 3) -> httpx.Response:
        if retries < 1:
            raise ValueError("retries must be at least 1")
        for attempt in range(retries):
            try:
                response = self.client.get(url, headers=headers, params=params)
                retryable = response.status_code == 429 or response.status_code >= 500
                if retryable and attempt + 1 < retries:
                    fallback = 5.0 if response.status_code == 429 else float(2**attempt)
                    time.sleep(retry_after_seconds(response.headers.get("Retry-After"), fallback=fallback))
                    continue
                if retryable:
                    try:
                        response_url = str(response.request.url)
                    except RuntimeError:
                        response_url = url
                    raise HttpRetryError(url=response_url, attempts=retries, status_code=response.status_code)
                return response
            except httpx.HTTPError as exc:
                if attempt + 1 < retries:
                    time.sleep(2**attempt)
                    continue
                raise HttpRetryError(url=url, attempts=retries, cause=exc) from exc
        raise HttpRetryError(url=url, attempts=retries)
