"""
Core chatbot logic: ties together intent recognition and the Gemini
client, keeps multi-turn context, and logs the session to a JSON file.

This module has no GUI code in it on purpose, so it can be tested and
reused independently of Tkinter (see test_chatbot.py).
"""

import json
import os
from datetime import datetime

from intent_handler import IntentHandler, extract_name
from gemini_client import GeminiClient, GeminiError

# How many previous turns (user+bot messages combined) to send to Gemini.
# Keeps the API request small instead of resending the whole conversation.
MAX_HISTORY_TURNS = 6

HISTORY_FILE = "chat_history.json"


class Chatbot:
    def __init__(self, intents_path="intents.json", history_file=HISTORY_FILE,
                 gemini_client=None):
        self.intent_handler = IntentHandler(intents_path)
        self.gemini = gemini_client if gemini_client is not None else GeminiClient()
        self.history_file = history_file
        self.context = self._fresh_context()
        self.session_log = []

    @staticmethod
    def _fresh_context():
        return {
            "user_name": None,
            "last_intent": None,
            "conversation_history": [],  # [{"role": "user"/"model", "text": ...}, ...]
        }

    def new_chat(self):
        """Start a brand new conversation context (clears memory and history)."""
        self.context = self._fresh_context()
        self.session_log = []

    def process_message(self, user_text):
        """
        Handle one user message end-to-end and return the bot's reply text.
        Never raises: any failure is turned into a friendly fallback reply.
        """
        if user_text is None or not user_text.strip():
            return "Please type a message before sending."

        cleaned_for_name = user_text.strip()
        name = extract_name(cleaned_for_name)
        if name:
            self.context["user_name"] = name

        intent = self.intent_handler.recognize_intent(user_text)
        self.context["last_intent"] = intent or "fallback"
        guidance = self.intent_handler.get_predefined_response(intent) if intent else None

        try:
            bot_reply = self.gemini.generate_reply(
                user_text=user_text,
                intent=intent,
                guidance=guidance,
                user_name=self.context["user_name"],
                history=self.context["conversation_history"][-MAX_HISTORY_TURNS:],
            )
        except GeminiError as e:
            bot_reply = str(e) if self._is_config_error(e) else self.intent_handler.get_fallback_response()

        self._record_turn(user_text, bot_reply, intent)
        return bot_reply

    @staticmethod
    def _is_config_error(e):
        """
        Config problems (missing/invalid key) should be shown verbatim so the
        user can fix setup. Transient issues fall back to a generic, friendly
        canned response instead of raw error text.
        """
        message = str(e).lower()
        return "api key" in message or "gemini_model" in message

    def _record_turn(self, user_text, bot_reply, intent):
        self.context["conversation_history"].append({"role": "user", "text": user_text})
        self.context["conversation_history"].append({"role": "model", "text": bot_reply})

        self.session_log.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": user_text,
            "intent": intent or "fallback",
            "bot": bot_reply,
        })
        self._save_history()

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({"session": self.session_log}, f, indent=2, ensure_ascii=False)
        except OSError:
            # Logging is a nice-to-have; a disk/permission issue shouldn't crash the chat.
            pass
