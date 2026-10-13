"""
Intent recognition.

Loads intents.json and figures out which intent (if any) a user's message
matches. The approach is a simple, explainable keyword/overlap scorer:
it is NOT machine learning, just comparing words in the user's message
against the example phrases stored in intents.json.
"""

import json
import random
import re

# Common words that don't carry much meaning for matching purposes.
# Removing them stops short "filler" words from causing false matches.
STOPWORDS = {
    "i", "a", "an", "is", "am", "are", "was", "were", "the", "to", "of",
    "what", "can", "you", "your", "yours", "me", "my", "do", "does", "did",
    "it", "that", "this", "how", "for", "in", "on", "and", "or", "so",
    "please", "could", "would", "should", "tell", "about", "like", "with",
}

# Shown when no intent matches confidently and Gemini also can't help.
FALLBACK_RESPONSES = [
    "I'm not sure I understand. Could you rephrase that?",
    "I'm not able to help with that yet. You can ask me about AI, Python, or what I can do.",
    "Hmm, I didn't quite catch that. Could you try asking in a different way?",
    "I'm still learning! Try asking me about AI, Python, or chatbots.",
]

# Patterns used to pull a name out of a sentence like "My name is Asmi."
_NAME_PATTERNS = [
    re.compile(r"\bmy name is\s+([a-zA-Z]+)", re.IGNORECASE),
    re.compile(r"\byou can call me\s+([a-zA-Z]+)", re.IGNORECASE),
    re.compile(r"\bcall me\s+([a-zA-Z]+)", re.IGNORECASE),
    re.compile(r"\bi am\s+([a-zA-Z]+)", re.IGNORECASE),
    re.compile(r"\bi'm\s+([a-zA-Z]+)", re.IGNORECASE),
]

# Words that follow "I am" / "I'm" far more often as a mood/state than a
# name (e.g. "I am tired"). Skipping these avoids obvious false positives.
_NON_NAME_WORDS = {
    "happy", "sad", "fine", "good", "great", "okay", "ok", "tired", "here",
    "ready", "sorry", "done", "busy", "back", "sure", "not", "so", "very",
    "just", "still", "also", "confused", "excited", "bored", "new",
}


def clean_text(text):
    """Lowercase, strip punctuation (but keep apostrophes), collapse spaces."""
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_name(text):
    """Return a capitalized name if the message introduces one, else None."""
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            candidate = match.group(1)
            if candidate.lower() in _NON_NAME_WORDS:
                continue
            return candidate.capitalize()
    return None


class IntentHandler:
    def __init__(self, json_path="intents.json"):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.intents = data["intents"]

    def recognize_intent(self, text):
        """
        Score every intent by how closely its example phrases match the
        user's message, and return the best match.

        For each example phrase, the match strength is the BEST of:
          1. Whole-phrase match: the example and the message contain each
             other as a sequence of whole words (not just a raw substring,
             so short examples like "yo" can't match inside "yourself") -> 2.0
          2. Word overlap: they share meaningful (non-stopword) words ->
             partial credit proportional to how much of the example's
             wording is covered.

        An intent's score is the single BEST-matching example it has, not
        the sum of all of them — otherwise an intent with many loosely
        related short examples could out-score a different intent with one
        exact, specific match.

        Returns the intent name with the highest score, or None if nothing
        scored high enough to be a confident match.
        """
        cleaned = clean_text(text)
        if not cleaned:
            return None

        padded_message = f" {cleaned} "
        message_words = set(cleaned.split()) - STOPWORDS

        best_intent = None
        best_score = 0.0

        for intent in self.intents:
            intent_best = 0.0
            for example in intent["examples"]:
                example_clean = clean_text(example)
                if not example_clean:
                    continue

                padded_example = f" {example_clean} "
                if padded_example in padded_message or padded_message in padded_example:
                    example_score = 2.0
                else:
                    example_words = set(example_clean.split()) - STOPWORDS
                    if not example_words:
                        example_score = 0.0
                    else:
                        overlap = message_words & example_words
                        example_score = len(overlap) / len(example_words) if overlap else 0.0

                intent_best = max(intent_best, example_score)

            if intent_best > best_score:
                best_score = intent_best
                best_intent = intent["intent"]

        # Require at least a reasonably strong signal before committing to
        # an intent; weak overlaps are treated as "not confident enough".
        if best_score >= 1.0:
            return best_intent
        return None

    def get_predefined_response(self, intent_name):
        for intent in self.intents:
            if intent["intent"] == intent_name:
                return random.choice(intent["responses"])
        return None

    def get_fallback_response(self):
        return random.choice(FALLBACK_RESPONSES)
