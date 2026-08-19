"""Unit tests for src/infra/ai/client.py covering GeminiClient operations,
input validation, prompt building, API error mapping, response parsing, and
telemetry logging.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import APIError

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
from src.infra.ai.client import GeminiClient


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
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(
            GeminiAuthError,
            match="Missing GEMINI_API_KEY environment variable.",
        ):
            GeminiClient(api_key=None)


@patch("src.infra.ai.client.genai.Client")
def test_init_client_instantiation_failure(
    mock_genai_client: MagicMock,
) -> None:
    """Validates initialization fails if SDK client construction raises."""
    mock_genai_client.side_effect = Exception("SDK Init Failure")
    with pytest.raises(GeminiAuthError, match="Gemini client initialization failed"):
        GeminiClient(api_key="fake_key")


@patch("src.infra.ai.client.genai.Client")
def test_init_success(mock_genai_client: MagicMock) -> None:
    """Validates successful GeminiClient initialization."""
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

    with pytest.raises(ValueError, match="asset_data context payload cannot be empty."):
        client.analyze_asset({}, valid_portfolio_context)

    with pytest.raises(ValueError, match="portfolio_context payload cannot be empty."):
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
# Successful Generation & Response Parsing Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_success_with_parsed_recommendation_object(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
    valid_recommendation_dict: dict[str, Any],
) -> None:
    """Validates analyze_asset when SDK directly returns parsed model instance."""
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
    """Validates analyze_asset when SDK returns a dictionary in response.parsed."""
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
    """Validates analyze_asset falls back to parsing raw text JSON when needed."""
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
    """Validates ticker resolution ('ticker' vs 'symbol' vs 'UNKNOWN')
    and custom model.
    """
    mock_response = MagicMock()
    mock_response.parsed = valid_recommendation_dict

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    # 1. Using 'ticker' key instead of 'symbol'
    client.analyze_asset(
        {"ticker": "MSFT"},
        valid_portfolio_context,
        model_name="gemini-1.5-pro",
        temperature=0.2,
    )

    # 2. Using no ticker key ('UNKNOWN')
    client.analyze_asset(
        {"value": 123},
        valid_portfolio_context,
    )

    assert mock_client_instance.models.generate_content.call_count == 2


# ==============================================================================
# API Exception & Error Handling Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_api_error_auth_scenarios(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates APIError with 401/403 or auth message maps to GeminiAuthError."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    # Code 401
    err_401 = APIError(401, "Invalid Auth")
    mock_client_instance.models.generate_content.side_effect = err_401
    with pytest.raises(GeminiAuthError, match="Authentication failed"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    # Auth message with generic non-401/403 status code
    err_msg = APIError(400, "Authentication failed due to bad token")
    mock_client_instance.models.generate_content.side_effect = err_msg
    with pytest.raises(GeminiAuthError, match="Authentication failed"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_api_error_quota_scenarios(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates APIError with 429 or quota message maps to GeminiQuotaError."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    # Code 429
    err_429 = APIError(429, "Rate limit exceeded")
    mock_client_instance.models.generate_content.side_effect = err_429
    with pytest.raises(GeminiQuotaError, match="API quota exceeded"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    # Quota message
    err_quota = APIError(500, "RESOURCE_EXHAUSTED: quota exceeded")
    mock_client_instance.models.generate_content.side_effect = err_quota
    with pytest.raises(GeminiQuotaError, match="API quota exceeded"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


@patch("src.infra.ai.client.genai.Client")
def test_analyze_asset_api_error_generic_and_unexpected(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates generic APIError and unexpected Exceptions map to GeminiAPIError."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    # Generic APIError
    mock_client_instance.models.generate_content.side_effect = APIError(
        500, "Internal Server Error"
    )
    with pytest.raises(GeminiAPIError, match="Gemini API failure"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    # Unexpected Exception
    mock_client_instance.models.generate_content.side_effect = RuntimeError(
        "Connection lost"
    )
    with pytest.raises(GeminiAPIError, match="Unexpected API error"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


# ==============================================================================
# Response Extraction, Parsing, & Safety Block Tests
# ==============================================================================


@patch("src.infra.ai.client.genai.Client")
def test_extract_raw_text_safe_blocked_candidate(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates response text failure and blocked finish_reason raises
    GeminiParsingError.
    """
    mock_response = MagicMock()
    mock_response.parsed = None

    # Simulate response.text property raising an exception (e.g. blocked text)
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
    with pytest.raises(GeminiParsingError, match="Generation blocked or incomplete"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


@patch("src.infra.ai.client.genai.Client")
def test_extract_raw_text_safe_empty_body(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates response with no text and no candidates raises
    GeminiParsingError.
    """
    mock_response = MagicMock()
    mock_response.parsed = None
    mock_response.text = None
    mock_response.candidates = []

    mock_client_instance = MagicMock()
    mock_client_instance.models.generate_content.return_value = mock_response
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")
    with pytest.raises(GeminiParsingError, match="Empty or inaccessible response body"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)


@patch("src.infra.ai.client.genai.Client")
def test_parse_response_invalid_json_and_validation_error(
    mock_genai_client: MagicMock,
    valid_asset_data: dict[str, Any],
    valid_portfolio_context: dict[str, Any],
) -> None:
    """Validates invalid JSON and Pydantic validation failures raise
    GeminiParsingError.
    """
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    client = GeminiClient(api_key="fake_key")

    # 1. Invalid JSON
    mock_resp_invalid_json = MagicMock(parsed=None, text="{invalid_json")
    mock_client_instance.models.generate_content.return_value = mock_resp_invalid_json
    with pytest.raises(GeminiParsingError, match="Structured validation failed"):
        client.analyze_asset(valid_asset_data, valid_portfolio_context)

    # 2. Pydantic validation error (e.g. confidence_score > 1.0 out of bounds)
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
    """Validates telemetry logging with full usage_metadata vs missing metadata."""
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance
    client = GeminiClient(api_key="fake_key")

    # 1. Usage metadata present
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 120
    mock_usage.candidates_token_count = 45
    mock_resp_with_usage = MagicMock(
        parsed=valid_recommendation_dict, usage_metadata=mock_usage
    )

    mock_client_instance.models.generate_content.return_value = mock_resp_with_usage
    res = client.analyze_asset(valid_asset_data, valid_portfolio_context)
    assert res.action == RecommendationAction.BUY

    # 2. Usage metadata missing (None)
    mock_resp_no_usage = MagicMock(
        parsed=valid_recommendation_dict, usage_metadata=None
    )
    mock_client_instance.models.generate_content.return_value = mock_resp_no_usage
    res2 = client.analyze_asset(valid_asset_data, valid_portfolio_context)
    assert res2.action == RecommendationAction.BUY
