# AI Chatbot (Intent Recognition + Gemini API)

An internship Task 1 project: a desktop chatbot that combines a simple,
explainable **intent-recognition system** with the **Google Gemini API**
for natural-language replies. It supports multi-turn context (including
remembering your name), logs each session to JSON, and never crashes on
bad input, a bad API key, or a network/API failure.

## Project objective & use case

Build a chatbot that:
- Recognizes a fixed set of common conversational intents (greetings,
  small talk, questions about AI/Python/chatbots, etc.) using transparent,
  hand-written logic — not a black box.
- Uses Gemini to turn those intents (plus the running conversation) into
  natural, varied replies instead of robotic canned text.
- Keeps a conversation going across multiple turns, remembering things
  like the user's name.
- Degrades gracefully — empty input, an unknown question, a missing/bad
  API key, or a Gemini outage should never crash the app.

## Features

- 12 intents defined in `intents.json`, each with multiple example
  triggers and predefined responses.
- Keyword/word-overlap intent recognition (see "How intent recognition
  works" below) — no exact-string-matching requirement, no ML library.
- Gemini API integration (`google-genai` SDK) for natural response
  generation, using the detected intent as a style hint.
- Multi-turn context: a capped conversation history window is sent to
  Gemini on every turn, and the user's name (once given) is remembered
  for the whole session.
- Fallback handling with multiple varied canned responses for when
  nothing can be understood.
- Tkinter chat GUI: scrollable chat log, visually distinct user/bot
  messages, Enter-to-send, Send/New Chat/Exit buttons.
- Session logging to `chat_history.json` (timestamp, user message,
  detected intent, bot reply) — the API key is never written to this file.
- Robust error handling for missing/invalid API keys, network failures,
  rate limits, and empty API responses, each with a short automatic retry
  for transient overload/rate-limit errors.
- `test_chatbot.py` with 20 diverse test inputs, split into local tests
  (no API calls) and opt-in live API tests.

## Architecture

```
User types in Tkinter window (main.py)
        |
        v
Chatbot.process_message()  (chatbot.py)
        |
        |-- extract_name() / intent_handler.recognize_intent()  (intent_handler.py)
        |        uses intents.json examples to find the best-matching intent
        |
        |-- builds: detected intent + predefined-response guidance +
        |           remembered user_name + capped conversation history
        v
GeminiClient.generate_reply()  (gemini_client.py)
        |
        v
Google Gemini API  -->  natural-language reply
        |
        v
Chatbot logs the turn to chat_history.json and returns the reply to the GUI
```

| File | Responsibility |
|---|---|
| `main.py` | Starts Tkinter, builds the GUI, wires clicks/Enter to the chatbot, displays replies |
| `chatbot.py` | Conversation context (name, last intent, history), orchestrates intent recognition + Gemini, logs the session |
| `intent_handler.py` | Loads `intents.json`, recognizes intents, extracts a stated name, supplies fallback text |
| `gemini_client.py` | Talks to the Gemini API, builds the prompt/context, translates failures into safe error messages |
| `intents.json` | The intent dataset: names, descriptions, example triggers, predefined responses |
| `chat_history.json` | Generated at runtime — this session's logged conversation |
| `test_chatbot.py` | Automated tests (local + live API) |

## Technologies used

- Python 3
- Google Gemini API via the official `google-genai` SDK
- Tkinter (standard library) for the GUI
- `python-dotenv` for loading the API key from `.env`
- JSON (standard library) for the intent dataset and chat log

## Gemini API setup

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Copy `.env.example` to a new file named `.env` in this folder.
3. Put your key in it:

   ```text
   GEMINI_API_KEY=your_api_key_here
   ```

   The app loads this with `python-dotenv` — **the key is never hard-coded
   anywhere in the source.** `.env` is listed in `.gitignore`, so it is
   never committed to version control.

### Which model, and why

The app defaults to `gemini-3.1-flash-lite`, set in `gemini_client.py` and
overridable via an optional `GEMINI_MODEL` entry in `.env`. During
development, `gemini-flash-latest` (which currently points at a preview
model) hit its **free-tier cap of only 20 requests per day** within a
single afternoon of testing — every call after that returned a `429
RESOURCE_EXHAUSTED` error (handled gracefully by the app, see "Error
handling" below, but obviously not great for a live demo). Google tracks
free-tier quota **per individual model**, so switching to
`gemini-3.1-flash-lite` gave the project its own, separate quota and
testing could continue. If you ever see a rate-limit fallback message
repeatedly, you've likely hit that model's daily cap — either wait for it
to reset or point `GEMINI_MODEL` at a different available model.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Your Gemini API key. Never commit this. |
| `GEMINI_MODEL` | No | Overrides the default model (`gemini-3.1-flash-lite`). |

## How to run

```bash
cd week2/ai-chatbot
pip install -r requirements.txt
# create .env from .env.example and add your key (see above)
python main.py
```

Type a message and press Enter or click **Send**. Use **New Chat** to
clear the conversation (including the remembered name) and start fresh.
**Exit** closes the app.

## All supported intents

| Intent | Purpose | Example triggers |
|---|---|---|
| `greeting` | User greets the chatbot | hello, hi, hey, good morning |
| `goodbye` | User ends the conversation | bye, goodbye, see you later |
| `ask_name` | User asks the chatbot's name | what is your name, who are you |
| `ask_capabilities` | User asks what the chatbot can do | what can you do, how can you help me |
| `ask_about_ai` | Questions about AI in general | what is ai, explain artificial intelligence |
| `ask_about_python` | Questions about Python | what is python, what can python be used for |
| `ask_about_chatbot` | Questions about how chatbots work | how do chatbots work, what is a chatbot |
| `help` | User requests help | help, i need help, can you help me |
| `thanks` | User expresses gratitude | thanks, thank you, appreciate it |
| `small_talk` | Casual conversation | how are you, tell me something interesting |
| `tell_name` *(extra)* | User states their own name | my name is, call me, i'm |
| `ask_my_name` *(extra)* | User asks the chatbot to recall their name | what is my name, do you remember my name |

`tell_name` and `ask_my_name` were added beyond the required 10 because
the assignment explicitly requires name memory ("My name is Asmi" → "What
is my name?"); giving that behavior its own intents keeps the dataset
honest about what triggers it, instead of hiding it inside `small_talk`.

The full dataset (with descriptions and response text) is in `intents.json`.

## How intent recognition works

`intent_handler.py` does **not** use machine learning or exact string
matching. For every intent, it compares the user's (lowercased,
punctuation-stripped) message against that intent's example phrases in
`intents.json`, and keeps the **best single match**:

1. **Whole-phrase match (score 2.0)** — the message and an example
   contain each other as a run of whole words (checked by padding both
   with spaces before comparing, so a short example like `"yo"` can't
   accidentally match inside an unrelated word like `"yourself"`).
2. **Word overlap (score 0–1)** — if there's no whole-phrase match, score
   = (shared meaningful words) ÷ (words in the example), after dropping
   filler words ("is", "the", "what", …) from both sides.

The intent with the highest score wins, provided that score is at least
`1.0`; otherwise `recognize_intent()` returns `None` and the chatbot
treats the message as unmatched (it still gets sent to Gemini — see
Fallback below).

Using the *best* single example rather than summing all of an intent's
examples matters: early in development, a message like `"My name is
Asmi"` was briefly misclassified as `ask_my_name` because that intent had
several loosely related examples whose small overlaps added up to beat
`tell_name`'s one exact match. Taking the max instead of the sum fixed it.

## Multi-turn context & name memory

`Chatbot` keeps an in-memory `context` dict for the session:

```python
context = {
    "user_name": None,
    "last_intent": None,
    "conversation_history": [],
}
```

- Every turn appends `{"role": "user", "text": ...}` and
  `{"role": "model", "text": ...}` to `conversation_history`.
- Only the **last 6 entries** (`MAX_HISTORY_TURNS` in `chatbot.py`) are
  sent to Gemini on the next call — enough for real multi-turn context
  (e.g. "What is Python?" → "What can I use it for?") without resending
  the whole conversation and burning extra API usage on every turn.
- `intent_handler.extract_name()` uses small regex patterns (`"my name
  is X"`, `"call me X"`, `"I'm X"`, etc.) to pull out a stated name,
  skipping common false positives like "I'm tired". Once known, the name
  is passed to Gemini on every later turn so it can answer "What is my
  name?" correctly.
- **New Chat** calls `Chatbot.new_chat()`, which resets the whole context
  dict (name, last intent, and history) for a clean slate.

## Fallback handling

If `recognize_intent()` returns `None` (no confident match), the chatbot
does **not** immediately give up — it still sends the message to Gemini,
since Gemini can often handle general questions outside the predefined
intents just fine. A canned fallback (randomly chosen from several
options in `intent_handler.FALLBACK_RESPONSES`) is only shown when Gemini
itself fails (see "Error handling"), or missing a chatbot-scoped intent
doesn't matter because Gemini answers it naturally anyway.

## Error handling

`gemini_client.py` catches every failure mode and converts it to a safe,
user-facing message — the app never crashes and the API key is never
included in any error text:

| Scenario | Behavior |
|---|---|
| Missing `GEMINI_API_KEY` | Clear message asking to set it in `.env` |
| Invalid/unauthorized key (401/403) | Message suggesting the key be checked |
| Rate limit / quota exceeded (429) | Friendly "try again later" message, after one short automatic retry |
| Server overloaded (5xx) | Friendly "temporarily overloaded" message, after one short automatic retry |
| Unknown model (404) | Message pointing at the `GEMINI_MODEL` setting |
| Network/connection failure | Generic "unable to connect" message |
| Empty response from Gemini | Message asking the user to rephrase |
| Empty user input | Caught in `chatbot.py` before any API call is made |

Config problems (missing/invalid key) are shown to the user verbatim,
since they need to actually fix their setup; transient issues (rate
limits, overload, network blips) instead show one of the generic
`FALLBACK_RESPONSES` so the chat doesn't read like a broken error log.

## Conversation history logging

Every turn is appended to `chat_history.json` as it happens:

```json
{
  "session": [
    {
      "timestamp": "2026-10-05 14:20:28",
      "user": "Hello",
      "intent": "greeting",
      "bot": "Hi there! It's great to meet you. How can I help you out today?"
    }
  ]
}
```

The file is overwritten with the growing session log on each turn (so it
always reflects the current session) and is listed in `.gitignore` since
it's generated output, not source code. It never contains the API key.

## Testing

`test_chatbot.py` is split into two parts, as required:

- **Local logic tests** (`TestIntentRecognition`, `TestChatbotLogic`) —
  run with plain `python -m unittest test_chatbot`. These never touch the
  network; a `FakeGeminiClient` stands in for the real API. They cover:
  - All 20 of the assignment's diverse test inputs and their expected
    intents (including two inputs that are expected to NOT match any
    intent locally).
  - Case/punctuation insensitivity and empty/whitespace input.
  - Name memory, multi-turn history being sent to Gemini, the history
    window being capped, `New Chat` resetting context, fallback behavior
    on a simulated Gemini error, and that the API key never appears in
    `chat_history.json`.
- **Live API tests** (`TestLiveGeminiAPI`) — skipped by default, so the
  normal test run costs zero API quota. Run them explicitly with:

  ```bash
  RUN_LIVE_API_TESTS=1 python main.py   # make sure .env is set up first
  RUN_LIVE_API_TESTS=1 python -m unittest test_chatbot.TestLiveGeminiAPI -v
  ```

  These make real Gemini calls to confirm a greeting gets a real reply
  and that name memory works end-to-end against the live API.

**Actual results from this project**, run on 2026-10-05: all 13 local
tests pass; both live tests pass using `gemini-3.1-flash-lite` (they
initially failed against `gemini-flash-latest` once its 20-request daily
free-tier quota was exhausted during development — see "Which model, and
why" above). A full manual run through "Hello" → "What is AI?" → "A
completely unknown question" → "Goodbye" against the real API produced
correct intents and natural, varied replies, and `chat_history.json`
logged all four turns correctly.

## Limitations

- Intent recognition is keyword/overlap-based, not true NLU — it won't
  resolve pronouns ("What can I use **it** for?" right after asking about
  Python) on its own. That specific case is exactly what the Gemini
  conversation history is for: the local matcher returns no intent, but
  Gemini still sees the prior turn and answers correctly.
- Name extraction uses simple regex patterns ("my name is X", "I'm X",
  etc.) and a short exclude-list for common non-name words after "I
  am"/"I'm" (e.g. "I am tired"). Unusual phrasing can still slip through.
- Free-tier Gemini quota is small and tracked per model (see above); the
  app handles running out of quota gracefully, but it does mean a long
  demo session could eventually need a different `GEMINI_MODEL` or a
  short wait.
- `chat_history.json` is overwritten per run, not appended across runs —
  it reflects the current session only, as the assignment asks for.

## How to demonstrate this during an internship review

1. Show `intents.json` and explain the 12 intents and their triggers.
2. Open the GUI, send a greeting, and point out the detected-intent-driven
   but naturally-phrased Gemini reply.
3. Say "My name is \<yours\>", then ask "What is my name?" to show context
   memory.
4. Ask "What is Python?" then immediately "What can I use it for?" to show
   multi-turn context resolving a pronoun Gemini wouldn't understand alone.
5. Type something nonsensical to show the fallback path, and briefly
   unset/break `GEMINI_API_KEY` in `.env` (then restore it) to show the
   friendly configuration-error message instead of a crash.
6. Click **New Chat** and show the name is forgotten — context truly reset.
7. Open `chat_history.json` to show the session log, and point out the API
   key is nowhere in the repo (`.env` is git-ignored) or in that file.
8. Run `python -m unittest test_chatbot -v` live to show the 20-input test
   suite passing without using any API quota.
