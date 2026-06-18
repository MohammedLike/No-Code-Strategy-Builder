"""Demo script: normalize raw strategy text via local LLM (Ollama)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.llm.normalizer import LLMNormalizer
from backend.app.strategy.compiler import compile_strategy

EXAMPLES = [
    "Buy BankNifty when SMA(20) crosses above SMA(50) on 15min chart. SL 1.5%, Target 3%. Exit when RSI(14) > 70.",
    "Sell Nifty Put option at 9:20 AM, strike ATM, expiry same week. SL 25%, Target 40%. Timeframe 5min.",
    "Long Nifty futures when RSI(14) < 25 and MACD line crosses above signal line on hourly chart. Trailing SL 1%.",
    "Buy when price breaks above the previous day high with volume surge. SL 0.5%. Target 2x risk. Daily timeframe.",
]


def main() -> None:
    normalizer = LLMNormalizer()

    if len(sys.argv) > 1:
        texts = [" ".join(sys.argv[1:])]
    else:
        texts = EXAMPLES

    for text in texts:
        print(f"\n{'='*60}")
        print(f"INPUT: {text}")
        print(f"{'='*60}")
        try:
            spec = normalizer.normalize_text(text)
            compiled = compile_strategy(spec)
            print(json.dumps(compiled.model_dump(mode="json", exclude_none=True), indent=2))
            status = "VALID" if compiled.validation.valid else "INVALID"
            print(f"\n>>> Compilation: {status}")
            if compiled.validation.errors:
                for err in compiled.validation.errors:
                    print(f"  - {err}")
        except Exception as e:
            print(f"ERROR: {e}")

    normalizer.close()


if __name__ == "__main__":
    main()
