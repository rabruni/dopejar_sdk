"""Tests for tier4_advanced modules (inference, llm_obs, evals, cost)."""
from __future__ import annotations

import pytest

from platform_sdk.tier4_advanced.cost import estimate_llm_cost, get_ledger
from platform_sdk.tier4_advanced.evals import (
    ContainsEvaluator,
    EvalSuite,
    ExactMatchEvaluator,
    LengthEvaluator,
)
from platform_sdk.tier4_advanced.inference import (
    Message,
    MockInferenceProvider,
    complete,
    embed,
)
from platform_sdk.tier4_advanced.llm_obs import MockLLMObsProvider, observe, record_inference


# ── inference ──────────────────────────────────────────────────────────────

class TestInference:
    @pytest.mark.asyncio
    async def test_mock_complete(self, mock_inference_provider):
        response = await mock_inference_provider.complete(
            __import__("platform_sdk.tier4_advanced.inference", fromlist=["InferenceRequest"]).InferenceRequest(
                messages=[Message(role="user", content="Hello")]
            )
        )
        assert response.content == "This is a mock LLM response."
        assert response.model == "mock-model"

    @pytest.mark.asyncio
    async def test_complete_public_api(self):
        response = await complete([
            Message(role="system", content="You are helpful."),
            Message(role="user", content="Say hi."),
        ])
        assert isinstance(response.content, str)
        assert response.total_tokens >= 0

    @pytest.mark.asyncio
    async def test_complete_accepts_dict_messages(self):
        response = await complete([
            {"role": "user", "content": "Hello"},
        ])
        assert isinstance(response.content, str)

    @pytest.mark.asyncio
    async def test_embed_returns_vectors(self):
        vectors = await embed(["hello world", "foo bar"])
        assert len(vectors) == 2
        assert all(isinstance(v, list) for v in vectors)
        assert all(len(v) > 0 for v in vectors)

    @pytest.mark.asyncio
    async def test_embed_single_string(self):
        vectors = await embed("just one text")
        assert len(vectors) == 1


# ── llm_obs ────────────────────────────────────────────────────────────────

class TestLLMObs:
    def test_observe_creates_trace(self, mock_llm_obs_provider):
        import platform_sdk.tier4_advanced.llm_obs as _obs
        _obs._provider = mock_llm_obs_provider
        trace = observe("test-pipeline")
        assert trace is not None
        assert len(mock_llm_obs_provider.traces) == 1

    def test_trace_generation_records_span(self, mock_llm_obs_provider):
        trace = mock_llm_obs_provider.create_trace("test")
        span = trace.generation(
            "llm_call",
            model="mock-model",
            input="Hello",
            output="World",
            usage={"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        )
        assert span.model == "mock-model"
        assert span.usage["total_tokens"] == 6

    def test_generation_span_has_cost_for_known_model(self, mock_llm_obs_provider):
        trace = mock_llm_obs_provider.create_trace("test")
        span = trace.generation(
            "llm_call",
            model="gpt-4o-mini",
            usage={"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200},
        )
        assert span.cost_usd > 0.0

    def test_generation_span_zero_cost_for_unknown_model(self, mock_llm_obs_provider):
        trace = mock_llm_obs_provider.create_trace("test")
        span = trace.generation(
            "llm_call",
            model="unknown-model-xyz",
            usage={"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200},
        )
        assert span.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_record_inference_helper(self, mock_llm_obs_provider):
        import platform_sdk.tier4_advanced.llm_obs as _obs
        _obs._provider = mock_llm_obs_provider

        response = await complete([Message(role="user", content="test")])
        span = record_inference("test-trace", response, user_id="u_123")
        assert span.model == response.model


# ── evals ──────────────────────────────────────────────────────────────────

class TestEvals:
    @pytest.mark.asyncio
    async def test_exact_match_pass(self):
        ev = ExactMatchEvaluator()
        result = await ev.evaluate("Hello World", expected="hello world")
        assert result.passed is True
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_fail(self):
        ev = ExactMatchEvaluator()
        result = await ev.evaluate("Hello World", expected="Goodbye World")
        assert result.passed is False
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_contains_evaluator(self):
        ev = ContainsEvaluator(["Python", "platform"])
        result = await ev.evaluate("This is a Python platform_sdk example.")
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_contains_missing(self):
        ev = ContainsEvaluator(["missing_keyword"])
        result = await ev.evaluate("Nothing relevant here.")
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_length_evaluator_pass(self):
        ev = LengthEvaluator(min_chars=5, max_chars=100)
        result = await ev.evaluate("Hello world!")
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_length_evaluator_fail_short(self):
        ev = LengthEvaluator(min_chars=20)
        result = await ev.evaluate("Hi")
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_eval_suite_all_pass(self):
        suite = EvalSuite([
            ContainsEvaluator(["hello"]),
            LengthEvaluator(min_chars=1),
        ])
        passed = await suite.passes("hello world")
        assert passed is True

    @pytest.mark.asyncio
    async def test_eval_suite_any_fail(self):
        suite = EvalSuite([
            ContainsEvaluator(["missing"]),
            LengthEvaluator(min_chars=1),
        ], require_all=True)
        passed = await suite.passes("hello world")
        assert passed is False


# ── cost ───────────────────────────────────────────────────────────────────

class TestCost:
    def test_estimate_known_model(self):
        cost = estimate_llm_cost("gpt-4o-mini", prompt_tokens=1000, completion_tokens=200)
        assert cost > 0.0

    def test_estimate_unknown_model_returns_zero(self):
        cost = estimate_llm_cost("unknown-model-xyz", prompt_tokens=1000, completion_tokens=200)
        assert cost == 0.0

    def test_ledger_record_and_retrieve(self):
        ledger = get_ledger()
        entry = ledger.record_llm(
            org_id="org-test",
            feature="chat",
            model="gpt-4o-mini",
            prompt_tokens=500,
            completion_tokens=100,
        )
        assert entry.cost_usd > 0.0
        assert ledger.get_spent("org-test") >= entry.cost_usd

    def test_ledger_budget_check(self):
        ledger = get_ledger()
        ledger.set_budget("org-budget-test", 0.001)
        ledger.record_llm(
            org_id="org-budget-test",
            feature="chat",
            model="gpt-4o",
            prompt_tokens=10000,
            completion_tokens=5000,
        )
        status = ledger.check_budget("org-budget-test")
        assert status.exceeded is True
