
"""
Arithmetic Formatter
--------------------
A tiny utility to neatly arrange a list of elementary arithmetic problems
vertically and side‑by‑side, optionally showing the answers.

Usage as a library:
    from arithmetic_formatter import arithmetic_formatter
    print(arithmetic_formatter(["32 + 698", "3801 - 2", "45 + 43", "123 + 49"], display_answers=True))

CLI usage:
    python -m arithmetic_formatter "32 + 8" "1 - 3801" --answers
"""
from typing import Iterable, List


class ArithmeticFormatterError(ValueError):
    pass


def _validate_problem(problem: str) -> None:
    parts = problem.split()
    if len(parts) != 3:
        raise ArithmeticFormatterError(f"Invalid problem format: {problem!r}. Expected 'operand operator operand'.")

    left, op, right = parts

    if op not in {"+", "-"}:
        raise ArithmeticFormatterError("Error: Operator must be '+' or '-'.")

    if not (left.isdigit() and right.isdigit()):
        raise ArithmeticFormatterError("Error: Numbers must only contain digits.")

    if len(left) > 4 or len(right) > 4:
        raise ArithmeticFormatterError("Error: Numbers cannot be more than four digits.")


def arithmetic_formatter(problems: Iterable[str], display_answers: bool = False, spacing: int = 4) -> str:
    """Arrange arithmetic problems vertically and side-by-side.

    Args:
        problems: An iterable of strings like "32 + 698".
        display_answers: If True, include a fourth line with the results.
        spacing: Number of spaces between problems.

    Returns:
        A single string with the formatted problems.

    Raises:
        ArithmeticFormatterError: If any validation rule fails.
    """
    problems = list(problems)

    if len(problems) == 0:
        return ""

    if len(problems) > 5:
        raise ArithmeticFormatterError("Error: Too many problems.")

    # Validate all problems first
    for p in problems:
        _validate_problem(p)

    line1: List[str] = []
    line2: List[str] = []
    dashes: List[str] = []
    results: List[str] = []

    for p in problems:
        left, op, right = p.split()
        width = max(len(left), len(right)) + 2  # operator + space + widest operand

        line1.append(left.rjust(width))
        line2.append(op + right.rjust(width - 1))
        dashes.append("-" * width)

        if display_answers:
            if op == "+":
                res = int(left) + int(right)
            else:
                res = int(left) - int(right)
            results.append(str(res).rjust(width))

    gap = " " * spacing
    arranged = gap.join(line1) + "\n" + gap.join(line2) + "\n" + gap.join(dashes)
    if display_answers:
        arranged += "\n" + gap.join(results)
    return arranged


def _demo():
    samples = ["32 + 698", "3801 - 2", "45 + 43", "123 + 49"]
    print(arithmetic_formatter(samples))
    print()
    print(arithmetic_formatter(samples, display_answers=True))


def main(argv: List[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Neatly arrange arithmetic problems.")
    parser.add_argument("problems", nargs="*", help="Problems like '32 + 698' (max 5).")
    parser.add_argument("-a", "--answers", action="store_true", help="Display answers.")
    parser.add_argument("-s", "--spacing", type=int, default=4, help="Spaces between problems (default: 4).")
    parser.add_argument("--demo", action="store_true", help="Show a quick demo output and exit.")
    args = parser.parse_args(argv)

    if args.demo:
        _demo()
        return 0

    try:
        print(arithmetic_formatter(args.problems, display_answers=args.answers, spacing=args.spacing))
    except ArithmeticFormatterError as e:
        print(str(e))
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
