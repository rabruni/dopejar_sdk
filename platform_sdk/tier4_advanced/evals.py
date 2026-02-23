"""
platform_sdk.tier4_advanced.evals
────────────────────────────────────
LLM output evaluation framework. Provides LLM-as-judge, rule-based,
and metric-based evaluators for validating model outputs in CI pipelines,
online monitoring, and A/B testing.

Backed by: DeepEval (OSS), Ragas (RAG evaluation), or custom LLM judge.

Minimal stack: DEFERRED — add when LLM output quality needs systematic
measurement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class EvalResult:
    passed: bool
    score: float        # 0.0–1.0
    reason: str = ""
    metric: str = ""
    metadata: dict[str, Any] | None = None


@runtime_checkable
class Evaluator(Protocol):
    async def evaluate(
        self,
        output: str,
        *,
        expected: str | None = None,
        context: list[str] | None = None,
        input: str | None = None,
    ) -> EvalResult: ...


class ExactMatchEvaluator:
    """Pass if output exactly matches expected (case-insensitive strip)."""

    async def evaluate(
        self,
        output: str,
        *,
        expected: str | None = None,
        context: list[str] | None = None,
        input: str | None = None,
    ) -> EvalResult:
        if expected is None:
            return EvalResult(passed=False, score=0.0, reason="No expected value provided", metric="exact_match")
        match = output.strip().lower() == expected.strip().lower()
        return EvalResult(
            passed=match,
            score=1.0 if match else 0.0,
            reason="Exact match" if match else f"Expected: {expected!r}, got: {output!r}",
            metric="exact_match",
        )


class ContainsEvaluator:
    """Pass if output contains all required strings."""

    def __init__(self, required: list[str], case_sensitive: bool = False) -> None:
        self._required = required
        self._cs = case_sensitive

    async def evaluate(
        self,
        output: str,
        *,
        expected: str | None = None,
        context: list[str] | None = None,
        input: str | None = None,
    ) -> EvalResult:
        check_output = output if self._cs else output.lower()
        missing = [
            r for r in self._required
            if (r if self._cs else r.lower()) not in check_output
        ]
        passed = len(missing) == 0
        score = 1.0 - (len(missing) / max(len(self._required), 1))
        return EvalResult(
            passed=passed,
            score=score,
            reason=f"Missing: {missing}" if missing else "All required strings found",
            metric="contains",
        )


class LengthEvaluator:
    """Pass if output length is within specified bounds."""

    def __init__(self, min_chars: int = 0, max_chars: int = 10_000) -> None:
        self._min = min_chars
        self._max = max_chars

    async def evaluate(
        self,
        output: str,
        *,
        expected: str | None = None,
        context: list[str] | None = None,
        input: str | None = None,
    ) -> EvalResult:
        length = len(output)
        passed = self._min <= length <= self._max
        score = 1.0 if passed else 0.0
        return EvalResult(
            passed=passed,
            score=score,
            reason=f"Length {length} {'in' if passed else 'outside'} [{self._min}, {self._max}]",
            metric="length",
        )


class RegexEvaluator:
    """Pass if output matches a regex pattern."""

    def __init__(self, pattern: str, flags: int = re.IGNORECASE) -> None:
        self._re = re.compile(pattern, flags)

    async def evaluate(
        self,
        output: str,
        *,
        expected: str | None = None,
        context: list[str] | None = None,
        input: str | None = None,
    ) -> EvalResult:
        match = bool(self._re.search(output))
        return EvalResult(
            passed=match,
            score=1.0 if match else 0.0,
            reason=f"Pattern {'matched' if match else 'not found'}: {self._re.pattern}",
            metric="regex",
        )


class EvalSuite:
    """Run multiple evaluators and aggregate results."""

    def __init__(self, evaluators: list[Evaluator], require_all: bool = True) -> None:
        self._evaluators = evaluators
        self._require_all = require_all

    async def run(
        self,
        output: str,
        *,
        expected: str | None = None,
        context: list[str] | None = None,
        input: str | None = None,
    ) -> list[EvalResult]:
        results = []
        for ev in self._evaluators:
            result = await ev.evaluate(
                output, expected=expected, context=context, input=input
            )
            results.append(result)
        return results

    async def passes(
        self,
        output: str,
        *,
        expected: str | None = None,
        context: list[str] | None = None,
        input: str | None = None,
    ) -> bool:
        results = await self.run(output, expected=expected, context=context, input=input)
        if self._require_all:
            return all(r.passed for r in results)
        return any(r.passed for r in results)


__all__ = [
    "EvalResult",
    "Evaluator",
    "ExactMatchEvaluator",
    "ContainsEvaluator",
    "LengthEvaluator",
    "RegexEvaluator",
    "EvalSuite",
]
