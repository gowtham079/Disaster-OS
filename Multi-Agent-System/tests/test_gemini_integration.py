"""Unit and Integration Tests for Gemini Integration & Environment Security.

Verifies:
1. Safe startup and controlled fallback when GEMINI_API_KEY is missing/empty (GEMINI_UNAVAILABLE).
2. Error resilience: API failure/timeout does not crash simulation.
3. Zero hardcoded API keys, secrets, or obsolete models (gemini-1.5-flash) in source.
4. .env.example contains only pure empty placeholders without secrets.
5. Gemini API key is never exposed in recommendation payloads or forwarded to the frontend.
6. AIAgent multi-agent integration functions smoothly on the MessageBus.
"""

import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from message_bus import AgentMessage, MessageBus
from ml.gemini_service import (
    DEFAULT_GEMINI_MODEL,
    DecisionSupportAgent,
    GeminiProvider,
    LocalHeuristicProvider,
    get_gemini_recommendation,
    get_llm_provider,
)
from models import AIRecommendation


class TestGeminiIntegration(unittest.TestCase):

    def setUp(self):
        # Ensure clean environment for deterministic testing
        self.original_gemini_key = os.environ.get("GEMINI_API_KEY")

    def tearDown(self):
        if self.original_gemini_key is not None:
            os.environ["GEMINI_API_KEY"] = self.original_gemini_key
        else:
            os.environ.pop("GEMINI_API_KEY", None)

    # 1. Missing GEMINI_API_KEY behavior
    def test_missing_gemini_key_reports_unavailable_safely(self):
        """When GEMINI_API_KEY is empty/missing, the provider must return LOCAL_HEURISTIC with GEMINI_UNAVAILABLE status."""
        os.environ["GEMINI_API_KEY"] = ""

        provider = get_llm_provider()
        self.assertIsInstance(provider, LocalHeuristicProvider)

        agent = DecisionSupportAgent()
        incident = {
            "location": "Coastal District Sector 7",
            "disaster_type": "flood",
            "severity": "high",
            "people_affected": 450,
        }
        allocation = {"teams_assigned": 6, "resources": ["Boats", "Ambulances"]}
        rescue = {}

        result = agent.get_explanation(incident, allocation, rescue)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("provider"), "LOCAL_HEURISTIC")
        self.assertEqual(result.get("status"), "GEMINI_UNAVAILABLE")
        self.assertEqual(result.get("model"), "local-rule-engine")
        self.assertIn("generated_at", result)
        self.assertIn("predicted_threat", result)
        self.assertIn("recommended_actions", result)
        self.assertGreaterEqual(len(result["recommended_actions"]), 2)

    # 2. Gemini provider error handling & fallback
    def test_gemini_api_failure_does_not_crash_and_falls_back(self):
        """When Gemini API call encounters an exception, it safely falls back to local heuristic."""
        os.environ["GEMINI_API_KEY"] = "fake_test_key_for_mocking"

        agent = DecisionSupportAgent()
        # Mock provider.generate to raise a runtime/API error simulating network timeout or quota exhaustion
        with patch.object(agent.provider, "generate", side_effect=RuntimeError("Simulated 503 Quota/Network error")):
            incident = {
                "location": "Sector 3",
                "disaster_type": "fire",
                "severity": "medium",
                "people_affected": 80,
            }
            allocation = {"teams_assigned": 3, "resources": ["Fire Engines"]}

            # Must NOT raise an exception
            result = agent.get_explanation(incident, allocation, rescue={})

            self.assertIsInstance(result, dict)
            self.assertEqual(result.get("provider"), "LOCAL_HEURISTIC")
            self.assertEqual(result.get("status"), "FALLBACK_TRIGGERED")
            self.assertIn("predicted_threat", result)
            self.assertIn("Fire", result["predicted_threat"])

    # 3. Model configuration
    def test_model_configuration_uses_current_flash_model(self):
        """The default model must be a modern Flash model (e.g. gemini-3.8-flash), never obsolete gemini-1.5-flash."""
        self.assertNotIn("1.5", DEFAULT_GEMINI_MODEL)
        self.assertIn("flash", DEFAULT_GEMINI_MODEL.lower())
        self.assertIn(DEFAULT_GEMINI_MODEL, ["gemini-3.8-flash", "gemini-2.5-flash"])

    # 4. Zero hardcoded secrets in source files
    def test_no_hardcoded_gemini_keys_or_urls_in_source(self):
        """Verify no hardcoded Gemini API keys or query string URLs exist in the codebase."""
        workspace_dir = Path(__file__).resolve().parent.parent.parent

        forbidden_patterns = [
            "gemini-1.5",
            "generativelanguage.googleapis.com",
            "AIzaSy",  # Standard Google API key prefix
        ]

        violations = []
        for root, dirs, files in os.walk(workspace_dir):
            if any(skip in root for skip in ["node_modules", ".git", "__pycache__", "build", "dist"]):
                continue
            for f in files:
                if f.endswith((".py", ".js", ".jsx", ".json", ".html")) and f != "test_gemini_integration.py":
                    file_path = Path(root) / f
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        for pattern in forbidden_patterns:
                            if pattern in content:
                                violations.append(f"{file_path}: contains '{pattern}'")
                    except Exception:
                        pass

        self.assertEqual(violations, [], f"Forbidden patterns found in source code: {violations}")

    # 5. .env.example contains only pure placeholders
    def test_env_example_contains_only_placeholders(self):
        """Verify .env.example has pure empty placeholders for sensitive keys."""
        example_path = Path(__file__).resolve().parent.parent / ".env.example"
        self.assertTrue(example_path.exists(), ".env.example must exist.")

        content = example_path.read_text(encoding="utf-8")
        self.assertIn("GEMINI_API_KEY=", content)
        self.assertIn("OPENWEATHER_API_KEY=", content)
        self.assertIn("SECRET_KEY=", content)

        for line in content.splitlines():
            line = line.strip()
            if line.startswith(("GEMINI_API_KEY=", "OPENWEATHER_API_KEY=", "ADMIN_TOKEN=")):
                parts = line.split("=", 1)
                self.assertEqual(parts[1].strip(), "", f"Secret placeholder {parts[0]} must be empty in .env.example")

    # 6. Gemini key is never sent to frontend / recommendation payloads
    def test_gemini_key_never_exposed_in_payloads(self):
        """Ensure recommendation payloads do not leak api_key or credentials."""
        os.environ["GEMINI_API_KEY"] = ""
        rec = get_gemini_recommendation()

        self.assertNotIn("api_key", rec)
        self.assertNotIn("key", rec)
        self.assertNotIn("secret", rec)

    # 7. AIAgent multi-agent integration
    def test_ai_agent_processes_message_with_provider_metadata(self):
        """Verify AIAgent receives COMMUNICATION_BROADCAST and publishes AI_RECOMMENDATION with metadata."""
        from agents import AIAgent

        bus = MessageBus()
        agent = AIAgent(bus)

        # Trigger message
        trigger_msg = AgentMessage(
            message_id="MSG-TRIGGER-1",
            sender="CommunicationAgent",
            message_type="COMMUNICATION_BROADCAST",
            payload={"alert_message": "High water levels in Sector 4"},
            timestamp="2026-09-20T12:00:00",
            priority=1,
        )

        agent.process_message(trigger_msg)

        # Verify AIAgent published AI_RECOMMENDATION to bus history
        self.assertGreaterEqual(len(bus.history), 1)
        rec_msg = next((m for m in bus.history if m.message_type == "AI_RECOMMENDATION"), None)
        self.assertIsNotNone(rec_msg)

        payload = rec_msg.payload
        self.assertIn("provider", payload)
        self.assertIn("model", payload)
        self.assertIn("generated_at", payload)
        self.assertIn("predicted_threat", payload)
        self.assertIn(payload.get("provider"), ["GEMINI", "LOCAL_HEURISTIC"])

    # 8. Thinking level configuration and metadata
    def test_gemini_thinking_level_metadata(self):
        """Verify thinking level is properly attached to provider metadata."""
        from ml.gemini_service import smoke_test_gemini
        res = smoke_test_gemini()
        self.assertIn("provider", res)
        self.assertIn("model", res)
        self.assertIn("thinking_level", res)
        if res.get("provider") == "GEMINI":
            self.assertEqual(res.get("model"), "gemini-3.8-flash")
            self.assertEqual(res.get("thinking_level"), "medium")
            self.assertIn(res.get("status"), ["OPERATIONAL", "TEMPORARILY_UNAVAILABLE", "ERROR"])


if __name__ == "__main__":
    unittest.main()
