"""
Automated tests for the chatbot.

Split into two groups, as required by the assignment:

1. Local logic tests (default `python -m unittest` run) — these never call
   the real Gemini API. They use a FakeGeminiClient stand-in so intent
   recognition, context/name memory, fallback behavior, empty-input
   handling, and history logging can all be verified without spending any
   API quota.

2. Live API integration tests — these DO call the real Gemini API and are
   skipped by default. Run them explicitly with:

       RUN_LIVE_API_TESTS=1 python -m unittest test_chatbot.TestLiveGeminiAPI
"""

import json
import os
import tempfile
import unittest

from dotenv import load_dotenv

load_dotenv()  # so TestLiveGeminiAPI picks up GEMINI_API_KEY from .env, same as main.py

from intent_handler import IntentHandler
from chatbot import Chatbot
from gemini_client import GeminiError


class FakeGeminiClient:
    """Stands in for GeminiClient so tests don't hit the network."""

    def __init__(self, reply="This is a fake reply.", raise_error=None):
        self.reply = reply
        self.raise_error = raise_error
        self.last_call = None  # records the arguments of the last call, for assertions

    def generate_reply(self, user_text, intent, guidance, user_name, history):
        self.last_call = {
            "user_text": user_text,
            "intent": intent,
            "guidance": guidance,
            "user_name": user_name,
            "history": history,
        }
        if self.raise_error:
            raise self.raise_error
        return self.reply


# The 20 diverse inputs required by the assignment, with the intent each
# one is expected to resolve to (None = no confident local match; the
# chatbot still falls through to Gemini or a canned fallback for these).
DIVERSE_INPUTS = [
    ("Hello", "greeting"),
    ("Hey there", "greeting"),
    ("Good morning", "greeting"),
    ("What is your name?", "ask_name"),
    ("What can you do?", "ask_capabilities"),
    ("What is AI?", "ask_about_ai"),
    ("Explain artificial intelligence", "ask_about_ai"),
    ("What is Python?", "ask_about_python"),
    ("What can Python be used for?", "ask_about_python"),
    ("Tell me about yourself", None),
    ("My name is Asmi", "tell_name"),
    ("What is my name?", "ask_my_name"),
    ("Thank you", "thanks"),
    ("Thanks for helping", "thanks"),
    ("I need help", "help"),
    ("Tell me something interesting", "small_talk"),
    ("What can you help me with?", "ask_capabilities"),
    ("A completely unknown question", None),
    ("What can I use it for?", None),  # follow-up; needs conversation context, not just keywords
    ("Goodbye", "goodbye"),
]


class TestIntentRecognition(unittest.TestCase):
    """Local-only: verifies the keyword/overlap intent matcher."""

    def setUp(self):
        self.handler = IntentHandler("intents.json")

    def test_all_20_diverse_inputs(self):
        for text, expected in DIVERSE_INPUTS:
            with self.subTest(text=text):
                self.assertEqual(self.handler.recognize_intent(text), expected)

    def test_empty_and_whitespace_input(self):
        self.assertIsNone(self.handler.recognize_intent(""))
        self.assertIsNone(self.handler.recognize_intent("   "))

    def test_case_and_punctuation_insensitive(self):
        self.assertEqual(self.handler.recognize_intent("HELLO!!!"), "greeting")
        self.assertEqual(self.handler.recognize_intent("  hello  "), "greeting")


class TestChatbotLogic(unittest.TestCase):
    """Local-only: chatbot orchestration using a FakeGeminiClient."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.history_path = os.path.join(self.tmp_dir.name, "chat_history.json")
        self.fake_gemini = FakeGeminiClient(reply="Hi! How can I help?")
        self.bot = Chatbot(
            intents_path="intents.json",
            history_file=self.history_path,
            gemini_client=self.fake_gemini,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_basic_reply_and_intent_detection(self):
        reply = self.bot.process_message("Hello")
        self.assertEqual(reply, "Hi! How can I help?")
        self.assertEqual(self.bot.context["last_intent"], "greeting")

    def test_empty_input_is_handled_without_calling_gemini(self):
        reply = self.bot.process_message("   ")
        self.assertIn("type a message", reply.lower())
        self.assertIsNone(self.fake_gemini.last_call)

    def test_name_memory(self):
        self.bot.process_message("My name is Asmi")
        self.assertEqual(self.bot.context["user_name"], "Asmi")

        self.bot.process_message("What is my name?")
        # The name should have been passed to Gemini for the follow-up turn.
        self.assertEqual(self.fake_gemini.last_call["user_name"], "Asmi")

    def test_multi_turn_context_is_sent_to_gemini(self):
        self.bot.process_message("What is Python?")
        self.bot.process_message("What can I use it for?")

        history_sent = self.fake_gemini.last_call["history"]
        # The first exchange (user + bot) should be present in the history
        # passed for the second call, proving context carries over.
        self.assertTrue(any(turn["text"] == "What is Python?" for turn in history_sent))

    def test_history_window_is_capped(self):
        for i in range(10):
            self.bot.process_message(f"Message number {i}")

        history_sent = self.fake_gemini.last_call["history"]
        self.assertLessEqual(len(history_sent), 6)  # MAX_HISTORY_TURNS in chatbot.py

    def test_fallback_on_transient_gemini_error(self):
        self.fake_gemini.raise_error = GeminiError("The AI service is temporarily overloaded.")
        reply = self.bot.process_message("Hello")
        # Should get one of the canned fallback responses, not a crash or raw error text.
        from intent_handler import FALLBACK_RESPONSES
        self.assertIn(reply, FALLBACK_RESPONSES)

    def test_config_error_is_shown_verbatim(self):
        self.fake_gemini.raise_error = GeminiError(
            "The chatbot isn't configured with a Gemini API key yet."
        )
        reply = self.bot.process_message("Hello")
        self.assertIn("API key", reply)

    def test_new_chat_resets_context(self):
        self.bot.process_message("My name is Asmi")
        self.assertEqual(self.bot.context["user_name"], "Asmi")

        self.bot.new_chat()
        self.assertIsNone(self.bot.context["user_name"])
        self.assertEqual(self.bot.context["conversation_history"], [])

    def test_conversation_history_logging(self):
        self.bot.process_message("Hello")
        self.bot.process_message("What is AI?")

        with open(self.history_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("session", data)
        self.assertEqual(len(data["session"]), 2)

        first_entry = data["session"][0]
        self.assertEqual(first_entry["user"], "Hello")
        self.assertEqual(first_entry["intent"], "greeting")
        self.assertEqual(first_entry["bot"], "Hi! How can I help?")
        self.assertIn("timestamp", first_entry)

        # The API key must never end up in the log.
        raw_text = json.dumps(data)
        self.assertNotIn("AQ.", raw_text)

    def test_unknown_input_still_reaches_gemini_for_a_natural_reply(self):
        reply = self.bot.process_message("A completely unknown question")
        self.assertEqual(reply, "Hi! How can I help?")  # fake client's canned reply
        self.assertEqual(self.bot.context["last_intent"], "fallback")


@unittest.skipUnless(
    os.getenv("RUN_LIVE_API_TESTS") == "1",
    "Set RUN_LIVE_API_TESTS=1 to run tests that call the real Gemini API.",
)
class TestLiveGeminiAPI(unittest.TestCase):
    """
    Integration tests against the real Gemini API.
    Skipped by default so the normal test run never consumes API quota.
    """

    def setUp(self):
        self.bot = Chatbot()

    def test_live_greeting_reply(self):
        reply = self.bot.process_message("Hello")
        self.assertTrue(len(reply) > 0)
        # Guards against a false pass where the "missing API key" error
        # message itself is non-empty text but no real API call happened.
        self.assertNotIn("api key", reply.lower())

    def test_live_name_memory(self):
        self.bot.process_message("My name is Asmi")
        reply = self.bot.process_message("What is my name?")
        self.assertIn("asmi", reply.lower())


if __name__ == "__main__":
    unittest.main()
