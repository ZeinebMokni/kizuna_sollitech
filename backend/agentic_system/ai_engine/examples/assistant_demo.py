"""Ask the QATRA assistant about the decision packages from decision_demo's farm.

Needs Claude API credentials (ANTHROPIC_API_KEY, or `ant auth login`). Each question makes a
few Claude API calls on claude-opus-5-5 and is billed to your account.
Usage: uv run python examples/assistant_demo.py "Why is the tomato zone first?"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from qatra_ai.assistant.assistant import QatraAssistant  # noqa: E402
from qatra_ai.assistant.tools import AssistantContext  # noqa: E402


def main() -> None:
    import decision_demo  # builds the real-data farm context

    question = " ".join(sys.argv[1:]) or "What should I do first today, and why?"
    env = decision_demo.build_decision()
    answer = QatraAssistant(AssistantContext(decision=env)).ask(question)
    print(answer.text)
    print(
        f"\n[verified={answer.verified} fallback={answer.used_fallback} "
        f"reason={answer.fallback_reason} citations={answer.citations} "
        f"tools={[c.name for c in answer.tool_calls]}]"
    )
    for v in answer.violations:
        print("  violation:", v)


if __name__ == "__main__":
    main()
