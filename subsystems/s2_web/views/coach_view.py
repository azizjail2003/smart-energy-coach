"""CoachView: everything the web interface shows from the S3 AI coach."""
from subsystems.s2_web.catalog import BUILDINGS, COACH_STATUSES, DEFAULT_BUILDING, MAX_QUESTION_LENGTH, TONES
from subsystems.s2_web.errors import ServiceUnavailableError

PREVIEW_QUESTION = "What should we change today?"
PREVIEW_TONE = "encouraging"
# S3 names its answer sources in lowercase; the chat shows them in words.
SOURCE_LABELS = {"openai": "OpenAI", "nvidia": "NVIDIA", "fallback": "Backup tips", "cached": "Cached answer"}


class CoachView:
    """Prepares the AI Coach page, the chat answers and the dashboard tip.

    The coach itself (S3) is a private attribute behind a property, so the
    view can be given a real coach, a mock or a replacement in tests.
    """

    def __init__(self, coach):
        self._coach = None
        self.coach = coach

    @property
    def coach(self):
        """The S3 AI coach this view talks to."""
        return self._coach

    @coach.setter
    def coach(self, value):
        for name in ("ask", "status", "tips"):
            if not callable(getattr(value, name, None)):
                raise TypeError(f"coach must provide a callable '{name}'.")
        self._coach = value

    def status(self):
        """Current coach availability with its label for the status badge."""
        status = self._coach.status()
        return {"status": status, "label": COACH_STATUSES[status]}

    def tips(self, building):
        return self._coach.tips(building)

    def page(self, building):
        """Template context for the AI Coach page."""
        status = self.status()
        return {
            "page": "coach",
            "building": building,
            "tones": TONES,
            "status": status["status"],
            "status_label": status["label"],
            "tips": self.tips(building),
            "max_length": MAX_QUESTION_LENGTH,
        }

    def ask(self, question, tone, building=DEFAULT_BUILDING):
        """Validate a chat request and return the coach's answer.

        Raises ValueError with a message meant for the user when the input is invalid.
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("'question' must be a non-empty text.")
        question = question.strip()
        if len(question) > MAX_QUESTION_LENGTH:
            raise ValueError(f"'question' must be at most {MAX_QUESTION_LENGTH} characters.")
        if not isinstance(tone, str) or tone not in TONES:
            raise ValueError(f"'tone' must be one of: {', '.join(TONES)}.")
        if not isinstance(building, str) or building not in BUILDINGS:
            raise ValueError(f"'building' must be one of: {', '.join(BUILDINGS)}.")

        result = self._ask_coach(question, tone, building)
        source = SOURCE_LABELS.get(result["source"], result["source"])
        live = source not in ("Backup tips", "Cached answer")
        return {
            "building": building,
            "question": question,
            "tone": tone,
            "answer": result["answer"],
            "source": source,
            "response_time_s": result.get("response_time_s") if live else None,
        }

    def _ask_coach(self, question, tone, building):
        """Ask S3; a lost connection or a timeout becomes a ServiceUnavailableError."""
        try:
            return self._coach.ask(question, tone, building)
        except (ConnectionError, TimeoutError) as error:
            raise ServiceUnavailableError("The AI coach did not answer. Try again in a moment.") from error

    def preview(self, building):
        """Headline and detail for the AI tip on the dashboard."""
        answer = self._ask_coach(PREVIEW_QUESTION, PREVIEW_TONE, building)["answer"]
        first, separator, rest = answer.partition(". ")
        if not separator:
            return answer, ""
        return first + ".", rest
