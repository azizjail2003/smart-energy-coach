from app.catalog import COACH_STATUSES
from . import mock_data as data

TONE_TEMPLATES = {
    "encouraging": "{action}. This saves about {saving_kwh} kWh per day (−{saving_pct}%) {benefit}.",
    "analytical": "{action}. Estimated effect: −{saving_kwh} kWh per day, {saving_pct}% of today's use, "
    "based on the hourly profile.",
    "strict": "{action}. Do it today: this removes {saving_kwh} kWh per day (−{saving_pct}%).",
}


def topic_of(question):
    text = question.lower()
    if "light" in text or "lamp" in text:
        return "lighting"
    if "server" in text:
        return "servers"
    return "heating"


class MockAICoach:
    """Provisional S3 (AI coach) interface. Returns canned answers; no AI service is called."""

    def __init__(self, status="online"):
        if status not in COACH_STATUSES:
            raise ValueError(f"Unknown coach status '{status}'.")
        self._status = status

    def status(self) -> str:
        return self._status

    def ask(self, question: str, tone: str, building_id: str) -> dict:
        if tone not in TONE_TEMPLATES:
            raise ValueError(f"Unknown tone '{tone}'.")
        if building_id not in data.COACH_ADVICE:
            raise ValueError(f"Unknown building '{building_id}'.")

        if self._status == "fallback":
            tip = self.tips(building_id)[0]
            return {"answer": f"The AI service is offline. Backup tip: {tip}.", "source": "Backup tips",
                    "response_time_s": None}

        advice = data.COACH_ADVICE[building_id][topic_of(question)]
        answer = TONE_TEMPLATES[tone].format(**advice)
        if self._status == "cached":
            return {"answer": answer, "source": "Cached answer", "response_time_s": None}
        return {"answer": answer, "source": data.COACH["source"], "response_time_s": data.COACH["response_time_s"]}

    def tips(self, building_id) -> list:
        return list(data.COACH_TIPS[building_id])
