"""Gemini AI API client implementation for structured investment analysis."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import ValidationError

from src.core.exceptions import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiParsingError,
    GeminiQuotaError,
)
from src.core.models import RebalanceRecommendation
from src.utils.logger.logger import logger

DEFAULT_MODEL: str = "gemini-2.5-flash"

SYSTEM_INSTRUCTION: str = (
    "You are an expert Quantitative Portfolio Manager and Asset Rebalancing "
    "Analyst. Your task is to analyze individual assets in the context of "
    "a user's portfolio and provide deterministic, data-driven rebalancing "
    "recommendations. You must strictly adhere to the requested JSON "
    "schema without adding conversational text, preamble, or markdown "
    "formatting."
)


class GeminiClient:
    """Enterprise-grade client wrapper for Google Gemini AI API interactions."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        """Initializes GeminiClient with API authentication and configuration."""
        resolved_key: str | None = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_key:
            logger.error("Gemini API key is missing from environment.")
            raise GeminiAuthError("Missing GEMINI_API_KEY environment variable.")

        self.model_name: str = model_name
        try:
            self._client: genai.Client = genai.Client(api_key=resolved_key)
        except Exception as err:
            logger.error(f"Failed to instantiate Gemini API client: {err}")
            raise GeminiAuthError(
                f"Gemini client initialization failed: {err}"
            ) from err

    def _validate_inputs(
        self,
        asset_data: dict[str, Any],
        portfolio_context: dict[str, Any],
    ) -> None:
        """Ensures incoming payload dicts contain minimum required attributes."""
        if not asset_data:
            raise ValueError("asset_data context payload cannot be empty.")
        if not portfolio_context:
            raise ValueError("portfolio_context payload cannot be empty.")

    def _build_prompt(
        self,
        asset_data: dict[str, Any],
        portfolio_context: dict[str, Any],
    ) -> str:
        """Constructs formatted user prompt payload from input metrics."""
        payload: dict[str, Any] = {
            "asset_info": asset_data,
            "portfolio_context": portfolio_context,
        }
        return json.dumps(payload, indent=2, default=str)

    def _clean_json_text(self, text: str) -> str:
        """Strips markdown code fences from raw LLM text response."""
        cleaned: str = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _extract_raw_text_safe(self, response: Any) -> str:
        """Safely extracts text from response guarding against safety blocks."""
        try:
            raw_text: str | None = getattr(response, "text", None)
            if raw_text:
                return raw_text
        except Exception as err:
            logger.warning(f"Direct response.text access failed: {err}")

        candidates: list[Any] | None = getattr(response, "candidates", None)
        if candidates and len(candidates) > 0:
            candidate: Any = candidates[0]
            finish_reason: Any = getattr(candidate, "finish_reason", None)
            if finish_reason and str(finish_reason) != "STOP":
                logger.error(
                    f"Gemini generation stopped abruptly. Reason: {finish_reason}"
                )
                raise GeminiParsingError(
                    f"Generation blocked or incomplete (reason: {finish_reason})."
                )

        raise GeminiParsingError("Empty or inaccessible response body from Gemini API.")

    def _log_telemetry(self, ticker: str, start_time: float, response: Any) -> None:
        """Logs execution latency and API token usage metrics."""
        elapsed_ms: float = (time.perf_counter() - start_time) * 1000
        token_info: str = "N/A"

        usage: Any = getattr(response, "usage_metadata", None)
        if usage:
            prompt_tokens: int = getattr(usage, "prompt_token_count", 0)
            candidate_tokens: int = getattr(usage, "candidates_token_count", 0)
            token_info = f"{prompt_tokens} in / {candidate_tokens} out"

        logger.info(
            f"Gemini analysis completed for '{ticker}' | "
            f"Latency: {elapsed_ms:.2f}ms | Tokens: {token_info}"
        )

    def analyze_asset(
        self,
        asset_data: dict[str, Any],
        portfolio_context: dict[str, Any],
        model_name: str | None = None,
        temperature: float = 0.1,
    ) -> RebalanceRecommendation:
        """Generates structured rebalancing analysis for a target asset.

        Args:
            asset_data: Fundamental and market data for the asset.
            portfolio_context: Portfolio allocations and total value.
            model_name: Optional override for the target Gemini model.
            temperature: Sampling temperature for output determinism.

        Returns:
            Validated RebalanceRecommendation instance.

        Raises:
            GeminiAuthError: If authentication fails.
            GeminiQuotaError: If API rate limits are hit.
            GeminiParsingError: If structured output validation fails.
            GeminiAPIError: For general API execution failures.
        """
        self._validate_inputs(asset_data, portfolio_context)

        target_model: str = model_name or self.model_name
        prompt: str = self._build_prompt(
            asset_data=asset_data,
            portfolio_context=portfolio_context,
        )

        config: types.GenerateContentConfig = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=RebalanceRecommendation,
            temperature=temperature,
        )

        ticker: str = str(asset_data.get("symbol", asset_data.get("ticker", "UNKNOWN")))
        logger.info(
            f"Requesting Gemini analysis for asset '{ticker}' "
            f"using model '{target_model}'"
        )
        start_time: float = time.perf_counter()

        try:
            response: Any = self._client.models.generate_content(
                model=target_model,
                contents=prompt,
                config=config,
            )
        except APIError as err:
            logger.error(f"Gemini API error during generation for '{ticker}': {err}")
            code: int | None = getattr(err, "code", None)
            err_msg: str = str(err).lower()

            if code in (401, 403) or "auth" in err_msg:
                raise GeminiAuthError(f"Authentication failed: {err}") from err
            if code == 429 or "quota" in err_msg:
                raise GeminiQuotaError(f"API quota exceeded: {err}") from err
            raise GeminiAPIError(f"Gemini API failure: {err}") from err
        except Exception as err:
            logger.error(f"Unexpected error calling Gemini API for '{ticker}': {err}")
            raise GeminiAPIError(f"Unexpected API error: {err}") from err

        self._log_telemetry(ticker=ticker, start_time=start_time, response=response)
        return self._parse_response(response=response)

    def _parse_response(self, response: Any) -> RebalanceRecommendation:
        """Extracts and validates RebalanceRecommendation from response."""
        if hasattr(response, "parsed") and response.parsed is not None:
            if isinstance(response.parsed, RebalanceRecommendation):
                return response.parsed
            if isinstance(response.parsed, dict):
                return RebalanceRecommendation.model_validate(response.parsed)

        raw_text: str = self._extract_raw_text_safe(response)
        cleaned_text: str = self._clean_json_text(raw_text)

        try:
            parsed_data: dict[str, Any] = json.loads(cleaned_text)
            return RebalanceRecommendation.model_validate(parsed_data)
        except (json.JSONDecodeError, ValidationError) as err:
            logger.error(f"Failed to parse Gemini response payload: {err}")
            raise GeminiParsingError(f"Structured validation failed: {err}") from err
