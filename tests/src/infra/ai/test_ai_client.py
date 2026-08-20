"""Unit tests for src/infra/ai/client.py.

Covers GeminiClient operations, input validation, prompt building,
batch prompting, API error mapping, retries, async execution,
response parsing, and telemetry logging.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai.errors import APIError

from src.config import settings
from src.core.exceptions import (
    GeminiAPIError,
    GeminiAuthError,
    GeminiParsingError,
    GeminiQuotaError,
)
from src.core.models import (
    RebalanceRecommendation,
    RecommendationAction,
    UrgencyLevel,
)
from src.infra.ai.client import (
    AssetRecommendationItem,
    BatchRebalanceRecommendations,
    GeminiClient,
)


@pytest.fixture
def valid_asset_data() -> dict[str, Any]:
    """Provides sample valid asset data payload."""
    return {
        "symbol": "AAPL",
        "current_price": 185.50,
        "pe_ratio": 28.4,
    }


@pytest.fixture
def valid_portfolio_context() -> dict[str, Any]:
    """Provides sample valid portfolio context payload."""
    return {
        "current_allocation_pct": 12.5,
        "target_allocation_pct": 8.0,
        "total_portfolio_value_eur": 15000.00,
    }


@pytest.fixture
def valid_recommendation_dict() -> dict[str, Any]:
    """Provides sample valid recommendation JSON response dictionary."""
    return {
        "action": "BUY",
        "confidence_score": 0.85,
        "reasoning": "Asset is undervalued relative to portfolio target.",
        "target_allocation_pct": 10.0,
        "urgency_level": "HIGH",
        "risk_score": 2,
        "valuation_score": 8,
        "expected_dividend_yield_pct": 1.5,
        "ter_impact_assessment": None,
    }


# ==============================================================================
# Initialization Tests
# ==============================================================================


def test_init_missing_api_key_raises_auth_error() -> None:
    """Validates initialization fails if API key is missing."""
    with patch.object(settings, "gemini_api_key", ""):
        with pytest.raises(
            GeminiAuthError,
            match="Missing GEMINI_API_KEY environment variable.",
        ):
            GeminiClient(api_key=None)


@patch("src.infra.ai.client.genai.Client")
def test_init_client_instantiation_failure(
    mock_genai_client: MagicMock,
) -> None:
    """Validates initialization fails if SDK construction raises."""
    mock_genai_client.side_effect = Exception("SDK Init Failure")
    err_msg: str = "Gemini client initialization failed"
    with pytest.raises(GeminiAuthError, match=err_msg):
        GeminiClient(api_key="fake_key")


@patch("src.infra.ai.client.genai.Client")
def test_init_success_with_default_and_custom_model(
    mock_genai_client: MagicMock,
) -> None:
    """Validates successful initialization using custom model."""
    client = GeminiClient(api_key="fake_key", model_name="custom-model")
    assert client.model_name == "custom-model"
    mock_genai_client.assert_called_once_with(api_key="fake_key")


# ==============================================================================
# Input Validation & Prompt Building Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_empty_inputs_raise_value_error(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates analyze_asset rejects empty payload dictionaries."""
    client = GeminiClient(api_key="fake_key")

    asset_err: str = "asset_data context payload cannot be empty."
    with pytest.raises(ValueError, match=asset_err):
        client.analyze_asset({}, valid_portfolio_context)

    port_err: str = "portfolio_context payload cannot be empty."
    with pytest.raises(ValueError, match=port_err):
        client.analyze_asset(valid_asset_data, {})


@patch("src.infra.ai.client.genai.Client")
def test_build_prompt_handles_non_serializable_objects(
    mock_genai_client: MagicMock,
) -> None:
    """Validates _build_prompt serializes custom non-standard objects."""
    client = GeminiClient(api_key="fake_key")

    class CustomObj:
        def __str__(self) -> str:
            return "custom_value"

    prompt = client._build_prompt(
        asset_data={"obj": CustomObj()},
        portfolio_context={"value": 100},
    )
    assert '"obj": "custom_value"' in prompt


def test_clean_json_text_variations() -> None:
    """Validates _clean_json_text strips markdown fences accurately."""
    client = GeminiClient.__new__(GeminiClient)

    plain_json = '{"key": "value"}'
    assert client._clean_json_text(plain_json) == '{"key": "value"}'

    fenced_json = '```json\n{"key": "value"}\n```'
    assert client._clean_json_text(fenced_json) == '{"key": "value"}'

    uppercase_fenced = '```JSON\n{"key": "value"}\n```'
    assert client._clean_json_text(uppercase_fenced) == '{"key": "value"}'

    generic_fenced = '```\n{"key": "value"}\n```'
    assert client._clean_json_text(generic_fenced) == '{"key": "value"}'


# ==============================================================================
# Batch Prompting Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_analyze_portfolio_batch_empty_inputs_raise_value_error(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates analyze_portfolio_batch rejects empty input parameters."""
    client = GeminiClient(api_key="fake_key")

    with pytest.raises(ValueError, match="assets_data payload list cannot be empty"):
        client.analyze_portfolio_batch([], valid_portfolio_context)

    with pytest.raises(ValueError, match="portfolio_context payload cannot be empty"):
        client.analyze_portfolio_batch([valid_asset_data], {})


@patch("src.infra.ai.client.genai.Client")
def test_analyze_portfolio_batch_success_with_parsed_object(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates analyze_portfolio_batch successfully parses batch response."""
    rec = RebalanceRecommendation.model_validate(valid_recommendation_dict)
    item = AssetRecommendationItem(symbol="AAPL", recommendation=rec)
    batch_container = BatchRebalanceRecommendations(items=[item])

    mock_response = MagicMock()
    mock_response.parsed = batch_container

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    result = client.analyze_portfolio_batch([valid_asset_data], valid_portfolio_context)

    assert "AAPL" in result
    assert result["AAPL"].action == RecommendationAction.BUY


@patch("src.infra.ai.client.genai.Client")
def test_analyze_portfolio_batch_success_with_parsed_dict_and_raw_fallback(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates batch parsing from dict and raw text fallback."""
    batch_payload = {
        "items": [
            {
                "symbol": "AAPL",
                "recommendation": valid_recommendation_dict,
            }
        ]
    }

    # Dict branch
    mock_response_dict = MagicMock(parsed=batch_payload)
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response_dict
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    res1 = client.analyze_portfolio_batch([valid_asset_data], valid_portfolio_context)
    assert "AAPL" in res1

    # Raw text fallback branch
    mock_response_raw = MagicMock(parsed=None, text=json.dumps(batch_payload))
    mock_client_instance.models.generate_content.return_value = mock_response_raw
    res2 = client.analyze_portfolio_batch([valid_asset_data], valid_portfolio_context)
    assert "AAPL" in res2


@patch("src.infra.ai.client.genai.Client")
def test_analyze_portfolio_batch_parsing_failure(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates batch parsing failure raises GeminiParsingError."""
    mock_response = MagicMock(parsed=None, text="{invalid_json_batch")
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    with pytest.raises(GeminiParsingError, match="Structured batch validation failed"):
        client.analyze_portfolio_batch([valid_asset_data], valid_portfolio_context)


# ==============================================================================
# Synchronous Generation & Response Parsing Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_success_with_parsed_recommendation_object(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates analyze_asset with parsed recommendation object."""
    expected_rec = RebalanceRecommendation.model_validate(valid_recommendation_dict)
    mock_response = MagicMock()
    mock_response.parsed = expected_rec

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    result = client.analyze_asset(valid_asset_data, valid_portfolio_context)

    assert result == expected_rec
    assert result.action == RecommendationAction.BUY


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_success_with_parsed_dict(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates analyze_asset when SDK returns a dictionary in parsed."""
    mock_response = MagicMock()
    mock_response.parsed = valid_recommendation_dict

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    result = client.analyze_asset(valid_asset_data, valid_portfolio_context)

    assert result.action == RecommendationAction.BUY
    assert result.confidence_score == 0.85


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_success_fallback_to_raw_text(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates analyze_asset falls back to parsing raw text JSON."""
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = json.dumps(valid_recommendation_dict)

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    result = client.analyze_asset(valid_asset_data, valid_portfolio_context)

    assert result.action == RecommendationAction.BUY
    assert result.urgency_level == UrgencyLevel.HIGH


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_ticker_resolution_and_custom_options(
    mock_genai_client: MagicMock,
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates ticker resolution ('ticker' vs 'symbol' vs 'UNKNOWN')."""
    mock_response = MagicMock()
    mock_response.parsed = valid_recommendation_dict

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    client.analyze_asset(
        {"ticker": "MSFT"},
        valid_portfolio_context,
        model_name="gemini-2.0-flash",
        temperature=0.2,
    )

    client.analyze_asset(
        {"value": 123},
        valid_portfolio_context,
    )

    assert mock_client_instance.models.generate_content.call_count == 2


# ==============================================================================
# Retry Mechanism & Error Handling Tests
# ==============================================================================


@patch("time.sleep", return_value=None)
@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_transient_error_retry_success(
    mock_genai_client: MagicMock,
    mock_sleep: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates retry mechanism succeeds after a transient 503 error."""
    mock_response = MagicMock()
    mock_response.parsed = valid_recommendation_dict

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.side_effect = [
        APIError(503, "Service Unavailable"),
        mock_response,
    ]
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    result = client.analyze_asset(valid_asset_data, valid_portfolio_context)

    assert result.action == RecommendationAction.BUY
    assert mock_client_instance.models.generate_content.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@patch("time.sleep", return_value=None)
@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_retry_exceeded_raises_quota_error(
    mock_genai_client: MagicMock,
    mock_sleep: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates exceeding MAX_RETRIES raises GeminiQuotaError."""
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.side_effect = APIError(
        429, "Rate limit exceeded"
    )
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    with pytest.raises(GeminiQuotaError, match="API quota exceeded"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    assert mock_client_instance.models.generate_content.call_count == 3


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_auth_error_no_retry(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates 401/403 auth errors fail immediately without retrying."""
    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.side_effect = APIError(
        401, "Invalid Auth"
    )
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    with pytest.raises(GeminiAuthError, match="Authentication failed"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    assert mock_client_instance.models.generate_content.call_count == 1


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_generic_and_unexpected_errors(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates API error mappings to GeminiAPIError."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    mock_client_instance.models.generate_content.side_effect = APIError(
        400, "Bad Request"
    )
    with pytest.raises(GeminiAPIError, match="Gemini API failure"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    mock_client_instance.models.generate_content.side_effect = RuntimeError(
        "Fatal socket error"
    )
    with pytest.raises(GeminiAPIError, match="Unexpected API error"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


# ==============================================================================
# Async Execution Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_async_success(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates asynchronous execution via analyze_asset_async."""
    mock_response = MagicMock()
    mock_response.parsed = valid_recommendation_dict

    mock_client_instance = MagicMock()
    mock_client_instance.aio.models.generate_content = AsyncMock(
        return_value=mock_response
    )
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    async def _runner() -> None:
        result = await client.analyze_asset_async(
            valid_asset_data, valid_portfolio_context
        )
        assert result.action == RecommendationAction.BUY

    asyncio.run(_runner())
    mock_client_instance.aio.models.generate_content.assert_called_once()


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_async_retry_and_auth_error(
    mock_genai_client: MagicMock,
    mock_async_sleep: AsyncMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates async retries and immediate auth error handling."""
    mock_response = MagicMock()
    mock_response.parsed = valid_recommendation_dict

    mock_client_instance = MagicMock()
    mock_client_instance.aio.models.generate_content = AsyncMock(
        side_effect=[APIError(500, "Server Error"), mock_response]
    )
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    async def _runner_success() -> None:
        result = await client.analyze_asset_async(
            valid_asset_data, valid_portfolio_context
        )
        assert result.action == RecommendationAction.BUY

    asyncio.run(_runner_success())
    assert mock_client_instance.aio.models.generate_content.call_count == 2
    mock_async_sleep.assert_called_once_with(1.0)

    # Auth Error
    mock_client_instance.aio.models.generate_content = AsyncMock(
        side_effect=APIError(403, "Forbidden")
    )

    async def _runner_auth() -> None:
        with pytest.raises(GeminiAuthError, match="Authentication failed"):
            await client.analyze_asset_async(valid_asset_data, valid_portfolio_context)

    asyncio.run(_runner_auth())


@patch("asyncio.sleep", new_callable=AsyncMock)
@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_async_quota_and_unexpected_error(
    mock_genai_client: MagicMock,
    mock_async_sleep: AsyncMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates async quota exhaustion and unexpected error mappings."""
    mock_client_instance = MagicMock()
    mock_client_instance.aio.models.generate_content = AsyncMock(
        side_effect=APIError(429, "Quota exceeded")
    )
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    async def _runner_quota() -> None:
        with pytest.raises(GeminiQuotaError, match="API quota exceeded"):
            await client.analyze_asset_async(valid_asset_data, valid_portfolio_context)

    asyncio.run(_runner_quota())

    mock_client_instance.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("Unexpected async crash")
    )

    async def _runner_unexpected() -> None:
        with pytest.raises(GeminiAPIError, match="Unexpected API error"):
            await client.analyze_asset_async(valid_asset_data, valid_portfolio_context)

    asyncio.run(_runner_unexpected())


# ==============================================================================
# Response Extraction, Parsing, & Safety Block Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_extract_raw_text_safe_blocked_candidate(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates blocked finish_reason raises GeminiParsingError."""
    mock_response = MagicMock()
    mock_response.parsed = None

    type(mock_response).text = property(
        fget=MagicMock(side_effect=ValueError("Quick response.text failure"))
    )

    mock_candidate = MagicMock()
    mock_candidate.finish_reason = "SAFETY"
    mock_response.candidates = [mock_candidate]

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    err_msg: str = "Generation blocked or incomplete"
    with pytest.raises(GeminiParsingError, match=err_msg):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


@patch("src.infra.ai.client.genai.Client")
def test_extract_raw_text_safe_empty_body(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates empty body response raises GeminiParsingError."""
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = None
    mock_response.candidates = []

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    err_msg: str = "Empty or inaccessible response body"
    with pytest.raises(GeminiParsingError, match=err_msg):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


@patch("src.infra.ai.client.genai.Client")
def test_parse_response_invalid_json_and_validation_error(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates parsing errors raise GeminiParsingError."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    mock_resp_invalid_json = MagicMock(parsed=None, text="{invalid_json")
    mock_client_instance.models.generate_content.return_value = mock_resp_invalid_json
    with pytest.raises(GeminiParsingError, match="Structured validation failed"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    mock_resp_out_of_bounds = MagicMock(
        parsed=None,
        text='{"action": "BUY", "confidence_score": 5.0, "reasoning": "R", '
        '"target_allocation_pct": 10.0, "urgency_level": "HIGH", '
        '"risk_score": 2, "valuation_score": 8}',
    )
    mock_client_instance.models.generate_content.return_value = mock_resp_out_of_bounds
    with pytest.raises(GeminiParsingError, match="Structured validation failed"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


# ==============================================================================
# Telemetry Logging Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_log_telemetry_with_and_without_usage_metadata(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates telemetry logging with full vs missing metadata."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    client = GeminiClient(api_key="fake_key")

    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 120
    mock_usage.candidates_token_count = 45
    mock_resp_with_usage = MagicMock(
        parsed=valid_recommendation_dict, usage_metadata=mock_usage
    )

    mock_client_instance.models.generate_content.return_value = mock_resp_with_usage
    res = client.analyze_asset(valid_asset_data, valid_portfolio_context)
    assert res.action == RecommendationAction.BUY

    mock_resp_no_usage = MagicMock(
        parsed=valid_recommendation_dict, usage_metadata=None
    )
    mock_client_instance.models.generate_content.return_value = mock_resp_no_usage
    res2 = client.analyze_asset(valid_asset_data, valid_portfolio_context)
    assert res2.action == RecommendationAction.BUY
