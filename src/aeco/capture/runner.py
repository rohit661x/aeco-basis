"""Daily capture driver. Fails loudly: a silent miss is unrecoverable data loss."""

from __future__ import annotations

import sys

from aeco.capture.sources import SOURCES, CaptureSource
from aeco.fetch import FetchError, capture


def run_all(
    sources: list[CaptureSource] | None = None, day: str | None = None
) -> dict[str, str]:
    results: dict[str, str] = {}
    for s in sources if sources is not None else SOURCES:
        try:
            capture(s.url, s.name, s.artifact, day=day, validator=s.validator)
            results[s.name] = "ok"
        except FetchError as e:
            results[s.name] = f"FAILED: {e}"
    return results


def main() -> int:
    results = run_all()
    for name, status in sorted(results.items()):
        print(f"ok       {name}" if status == "ok" else f"{name}: {status}")
    failures = [n for n, s in results.items() if s != "ok"]
    if failures:
        print(f"\n{len(failures)} source(s) failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
