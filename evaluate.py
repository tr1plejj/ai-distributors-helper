from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_GOLDEN_PATH = Path("tests/golden_questions.json")


@dataclass
class CaseResult:
    name: str
    question: str
    passed: bool
    missing: list[str]
    forbidden: list[str]
    answer: str


def main() -> None:
    parser = argparse.ArgumentParser(description="Run golden-question evaluation for the assistant.")
    parser.add_argument("--file", default=str(DEFAULT_GOLDEN_PATH), help="Path to golden questions JSON.")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N questions.")
    parser.add_argument("--limit", type=int, default=None, help="Run only first N questions.")
    parser.add_argument("--initial-delay", type=float, default=0.0, help="Seconds to wait before the first question.")
    parser.add_argument("--pause", type=float, default=2.0, help="Seconds to wait between questions.")
    parser.add_argument("--retries", type=int, default=3, help="Retries for OpenAI rate limits.")
    parser.add_argument("--retry-delay", type=float, default=8.0, help="Fallback retry delay in seconds.")
    parser.add_argument("--show-answers", action="store_true", help="Print full model answers.")
    args = parser.parse_args()

    cases = _load_cases(Path(args.file))
    cases = cases[args.offset :]

    if args.limit is not None:
        cases = cases[: args.limit]

    answer_question, data = _load_assistant()
    results = []

    if args.initial_delay > 0:
        print(f"Waiting {args.initial_delay:.1f}s before the first question...")
        time.sleep(args.initial_delay)

    for index, case in enumerate(cases, start=1):
        case_number = args.offset + index
        print(f"{case_number}. RUN {case['name']}")
        print(f"   question: {case['question']}")

        result = _run_case(case, data, answer_question, retries=args.retries, retry_delay=args.retry_delay)
        results.append(result)
        _print_result(result, case_number, show_answer=args.show_answers)

        if args.pause > 0 and index < len(cases):
            time.sleep(args.pause)

    passed_count = sum(result.passed for result in results)
    total_count = len(results)
    score = round(passed_count / total_count, 2) if total_count else 0

    print()
    print(f"Score: {passed_count}/{total_count} ({score})")

    if passed_count != total_count:
        raise SystemExit(1)


def _print_result(result: CaseResult, case_number: int, show_answer: bool) -> None:
    status = "PASS" if result.passed else "FAIL"
    print(f"{case_number}. {status} {result.name}")

    if result.missing:
        print(f"   missing: {', '.join(result.missing)}")
    if result.forbidden:
        print(f"   forbidden: {', '.join(result.forbidden)}")
    if show_answer:
        print("   answer:")
        print(_indent(result.answer, "   "))


def _load_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_assistant():
    try:
        from dotenv import load_dotenv

        from src.cleaning import prepare_data
        from src.data_sources import fetch_orders, fetch_products, load_clients
        from src.llm import answer_question
    except ModuleNotFoundError as error:
        raise SystemExit(f"Missing dependency: {error.name}. Run: pip install -r requirements.txt") from error

    load_dotenv()
    data = prepare_data(load_clients(), fetch_products(), fetch_orders())
    return answer_question, data


def _run_case(case: dict, data, answer_question, retries: int, retry_delay: float) -> CaseResult:
    answer = _answer_with_retries(
        answer_question=answer_question,
        question=case["question"],
        data=data,
        retries=retries,
        retry_delay=retry_delay,
    )
    missing = [item for item in case.get("must_contain", []) if not _contains(answer, item)]
    forbidden = [item for item in case.get("must_not_contain", []) if _contains(answer, item)]

    return CaseResult(
        name=case["name"],
        question=case["question"],
        passed=not missing and not forbidden,
        missing=missing,
        forbidden=forbidden,
        answer=answer,
    )


def _answer_with_retries(answer_question, question: str, data, retries: int, retry_delay: float) -> str:
    attempt = 0

    while True:
        try:
            return answer_question(question, data)
        except Exception as error:
            if not _is_rate_limit_error(error) or attempt >= retries:
                raise

            delay = _retry_delay_from_error(error) or retry_delay
            attempt += 1
            print(
                f"Rate limit reached. Retry {attempt}/{retries} in {delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)


def _is_rate_limit_error(error: Exception) -> bool:
    return error.__class__.__name__ == "RateLimitError" or "rate_limit" in str(error).lower()


def _retry_delay_from_error(error: Exception) -> float | None:
    match = re.search(r"try again in ([0-9.]+)s", str(error), flags=re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1)) + 1


def _contains(text: str, expected: str) -> bool:
    normalized_text = _normalize(text)
    normalized_expected = _normalize(expected)

    if normalized_expected in normalized_text:
        return True

    return _compact(normalized_expected) in _compact(normalized_text)


def _normalize(value: str) -> str:
    value = value.lower().replace("ё", "е").replace(",", ".")
    value = value.replace("\u00a0", " ").replace("\u202f", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _indent(value: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in value.splitlines())


if __name__ == "__main__":
    main()
