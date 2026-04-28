from __future__ import annotations

import os
import unittest

from ultron_mini import launcher


class LauncherPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def test_quick_prompt_uses_small_budget(self) -> None:
        os.environ["BRAIN_DYNAMIC_MAX_TOKENS"] = "1"
        os.environ["BRAIN_TOKENS_QUICK"] = "192"
        os.environ["BRAIN_MAX_TOKENS_CAP"] = "768"

        tokens = launcher._select_max_tokens(
            messages=[{"role": "user", "content": "hi"}],
            tools=None,
            base_tokens=512,
        )

        self.assertEqual(tokens, 192)

    def test_plan_prompt_uses_larger_budget(self) -> None:
        os.environ["BRAIN_DYNAMIC_MAX_TOKENS"] = "1"
        os.environ["BRAIN_TOKENS_PLAN"] = "512"
        os.environ["BRAIN_MAX_TOKENS_CAP"] = "768"

        tokens = launcher._select_max_tokens(
            messages=[{"role": "user", "content": "Explain the architecture and strategy in detail."}],
            tools=None,
            base_tokens=256,
        )

        self.assertEqual(tokens, 512)

    def test_persona_text_stays_short(self) -> None:
        persona = launcher._persona_text()
        self.assertLess(len(persona.splitlines()), 10)
        self.assertIn("Ultron-mini", persona)


if __name__ == "__main__":
    unittest.main()
