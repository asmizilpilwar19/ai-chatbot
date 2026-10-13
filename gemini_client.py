"""
Thin wrapper around the Gemini API.

Responsible for:
- Reading the API key from the environment (never hard-coded).
- Sending the conversation (system instructions + recent history + new
  message) to Gemini.
- Translating any failure (missing key, bad key, network issue, rate
  limit, server overload, empty reply) into a GeminiError with a safe,
  user-friendly message that never includes the API key.
"""

import os
import time

from google import genai
from google.genai import errors, types

DEFAULT_MODEL = "gemini-3.1-flash-lite"

# The free tier occasionally returns 503 "overloaded" or 429 "rate limited"
# for a request that would otherwise succeed. One short retry smooths over
# that without masking a real, persistent problem (like a bad API key).
RETRYABLE_CODES = {429, 503}
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 1.5


class GeminiError(Exception):
    """Raised whenever Gemini can't produce a usable reply."""


class GeminiClient:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self._client = None

        if api_key:
            self._client = genai.Client(api_key=api_key)

    def generate_reply(self, user_text, intent, guidance, user_name, history):
        """
        Ask Gemini for a reply.

        - user_text: the new message the human just typed.
        - intent: the intent we detected locally (or None).
        - guidance: a predefined response for that intent, used as a style
          hint rather than something Gemini must repeat verbatim.
        - user_name: the user's name if we know it, else None.
        - history: a list of {"role": "user"/"model", "text": ...} dicts,
          already trimmed to a reasonable window by chatbot.py.
        """
        if self._client is None:
            raise GeminiError(
                "The chatbot isn't configured with a Gemini API key yet. "
                "Please add GEMINI_API_KEY to your .env file."
            )

        system_instruction = self._build_system_instruction(intent, guidance, user_name)
        contents = self._build_contents(history, user_text)
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=300,
        )

        response = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model_name, contents=contents, config=config
                )
                break
            except errors.APIError as e:
                code = getattr(e, "code", None)
                if code in RETRYABLE_CODES and attempt < MAX_ATTEMPTS:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                raise GeminiError(self._friendly_message_for(e)) from e
            except Exception as e:
                # Covers network issues (no internet, DNS failure, timeouts, etc.)
                raise GeminiError(
                    "Unable to connect to the AI service right now. Please check your "
                    "internet connection and try again."
                ) from e

        text = (response.text or "").strip() if response else ""
        if not text:
            raise GeminiError(
                "The AI service returned an empty response. Please try rephrasing your message."
            )
        return text

    @staticmethod
    def _build_system_instruction(intent, guidance, user_name):
        parts = [
            "You are a friendly, concise AI chatbot built for an internship demo. "
            "Keep replies natural and short (1-3 sentences) unless the user asks for detail. "
            "Stay within the chatbot's intended scope: general conversation, and questions "
            "about AI, Python, and chatbots.",
        ]
        if user_name:
            parts.append(f"The user's name is {user_name}. Use it naturally if relevant.")
        if intent:
            parts.append(
                f"Our local system detected the intent '{intent}' for the user's latest "
                f"message."
            )
        if guidance:
            parts.append(
                f"A predefined response we'd normally give for this kind of message is: "
                f"\"{guidance}\". Use it as inspiration for tone and content, but reply "
                f"naturally in your own words rather than copying it exactly."
            )
        return " ".join(parts)

    @staticmethod
    def _build_contents(history, user_text):
        contents = []
        for turn in history:
            contents.append(
                types.Content(role=turn["role"], parts=[types.Part.from_text(text=turn["text"])])
            )
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))
        return contents

    @staticmethod
    def _friendly_message_for(e):
        code = getattr(e, "code", None)
        if code in (401, 403):
            return (
                "The Gemini API key appears to be invalid or unauthorized. Please check "
                "the GEMINI_API_KEY value in your .env file."
            )
        if code == 429:
            return "The AI service is rate-limited right now. Please wait a moment and try again."
        if code == 404:
            return "The configured Gemini model isn't available. Please check the GEMINI_MODEL setting."
        if code is not None and code >= 500:
            return "The AI service is temporarily overloaded. Please try again in a moment."
        return "The AI service couldn't process that request. Please try again."
