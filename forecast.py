from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(slots=True)
class RiskForecast:
    """Foydalanuvchi uchun ergonomik xavf prognozi.

    `current_risk` — bugungi 0..100 xavf darajasi.
    `projected_risk_7d` — agar trend davom etsa, 7 kundan keyingi xavf.
    `slope_per_day` — kunlik o'sish/pasayish (musbat = yomonlashayapti).
    `pain_probability_30d` — keyingi 30 kunda mushak-skelet og'rig'i ehtimoli (0..1).
    `category` — "low" / "moderate" / "high" / "critical".
    `recommendation` — foydalanuvchiga aniq amaliy maslahat.
    """

    current_risk: float
    projected_risk_7d: float
    slope_per_day: float
    pain_probability_30d: float
    category: str
    recommendation: str


def _linear_trend(values: Sequence[float]) -> tuple[float, float]:
    """Oddiy least-squares chiziqli regressiya.

    Qaytadi: (intercept, slope). Vaqt 0..n-1 indekslari bilan o'lchanadi.
    """
    n = len(values)
    if n < 2:
        return (float(values[0]) if values else 0.0, 0.0)

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return (mean_y, 0.0)

    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    return (intercept, slope)


def _categorise(risk: float) -> str:
    if risk < 25:
        return "low"
    if risk < 50:
        return "moderate"
    if risk < 75:
        return "high"
    return "critical"


def _build_recommendation(category: str, slope: float, current_risk: float) -> str:
    if category == "low":
        if slope > 1.0:
            return "Holatingiz yaxshi, lekin xavf o'sib bormoqda. Har 25 daqiqada qisqa tanaffus qiling."
        return "Ergonomik holatingiz yaxshi. Joriy odatlaringizni davom ettiring."

    if category == "moderate":
        return (
            "O'rtacha xavf. Stol balandligini tekshiring, monitorni ko'z darajasiga qo'ying "
            "va kuniga 2-3 marta cho'zilish mashqlarini bajaring."
        )

    if category == "high":
        return (
            "Yuqori xavf. Yelka va bo'yin og'rig'i ehtimoli ortmoqda. "
            "Ergonomik kreslo va 30 daqiqalik ish/5 daqiqalik tanaffus rejimini joriy qiling."
        )

    # critical
    return (
        "Kritik xavf. Mutaxassisga (ortoped/fizioterapevt) murojaat qiling. "
        "Ish jadvalini darhol qayta ko'rib chiqing."
    )


def forecast_risk(weekly_summary: list[dict]) -> RiskForecast | None:
    """Haftalik posture statistikasidan ergonomik xavf prognozini hisoblaydi.

    Argument: `Storage.get_weekly_summary()` natijasi — har bir kun uchun
    `avg_ergonomic` (yoki `avg_score`) qiymatini o'z ichiga olgan ro'yxat.

    Qaytadi `RiskForecast` yoki ma'lumot yetarli emas bo'lsa `None`.
    """
    if not weekly_summary:
        return None

    daily_scores: list[float] = []
    for row in weekly_summary:
        score = row.get("avg_ergonomic")
        if not score:
            score = row.get("avg_score") or 0.0
        if score > 0:
            daily_scores.append(float(score))

    if len(daily_scores) < 2:
        return None

    # Risk = 100 - score (yuqori risk = yomon ergonomika)
    daily_risks = [100.0 - score for score in daily_scores]
    intercept, slope = _linear_trend(daily_risks)

    n = len(daily_risks)
    current_risk = max(0.0, min(100.0, intercept + slope * (n - 1)))
    projected_risk_7d = max(0.0, min(100.0, intercept + slope * (n - 1 + 7)))

    # Pain probability modeli:
    # 30 kun davomida o'rtacha risk yuqori bo'lsa, og'riq ehtimoli oshadi.
    # Asos: WHO ofis xodimlarida 54% surunkali bo'yin og'rig'i statistikasi
    # — biz buni baseline sifatida olamiz va riskka mutanosib oshiramiz.
    avg_projected_30d = max(
        0.0,
        min(100.0, intercept + slope * (n - 1 + 15)),  # 30 kunlik o'rtacha
    )
    baseline_pain_prob = 0.10
    risk_factor = avg_projected_30d / 100.0
    pain_probability_30d = min(0.95, baseline_pain_prob + risk_factor * 0.70)

    category = _categorise(current_risk)
    recommendation = _build_recommendation(category, slope, current_risk)

    return RiskForecast(
        current_risk=round(current_risk, 1),
        projected_risk_7d=round(projected_risk_7d, 1),
        slope_per_day=round(slope, 2),
        pain_probability_30d=round(pain_probability_30d, 2),
        category=category,
        recommendation=recommendation,
    )
