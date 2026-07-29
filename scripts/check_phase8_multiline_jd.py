from __future__ import annotations

from tailoring.phase8_verification import _normalise_multiline_text


def main() -> int:
    source = (
        "\r\nJob Description\r\n\r\n"
        "Operate and maintain the product.\r\n\r\n"
        "Job Requirements\r\n\r\n"
        "Minimum 1 year of experience.\r\n"
    )
    expected = (
        "Job Description\n\n"
        "Operate and maintain the product.\n\n"
        "Job Requirements\n\n"
        "Minimum 1 year of experience."
    )
    actual = _normalise_multiline_text(source)

    passed = actual == expected
    print("Preserved line count:", len(actual.splitlines()))
    print("Contains section boundary:", "\n\nJob Requirements\n\n" in actual)
    print(
        "PHASE 8 MULTILINE JD PRESERVATION:",
        "PASS" if passed else "FAIL",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
