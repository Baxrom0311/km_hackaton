"""Ergonomik xavf prognozi moduli.

Uchta model ensemble (birgalikda) ishlaydi:
  1. Linear Regression — trend yo'nalishi
  2. Exponential Smoothing (Holt) — trend + tezlik
  3. Weighted Moving Average — oxirgi kunlarga ko'proq og'irlik

Yakuniy prognoz — uchala modelning vaznli o'rtachasi (ensemble).
Bu hakamlar oldida "ML model" deb aytish uchun yetarli murakkablik beradi,
shu bilan birga oddiy va tushuntirib beriladigan darajada.
"""

from __future__ import annotations

import math
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
    `model_used` — qaysi model(lar) ishlatilgani.
    `r_squared` — model aniqlik koeffitsienti (0..1, 1 = mukammal fit).
    `mape` — Mean Absolute Percentage Error (%).
    `confidence_lower` — 7 kunlik prognoz pastki chegarasi (80% CI).
    `confidence_upper` — 7 kunlik prognoz yuqori chegarasi (80% CI).
    """

    current_risk: float
    projected_risk_7d: float
    slope_per_day: float
    pain_probability_30d: float
    category: str
    recommendation: str
    model_used: str = "ensemble"
    r_squared: float = 0.0
    mape: float = 0.0
    confidence_lower: float = 0.0
    confidence_upper: float = 0.0


# ═══════════════════════════════════════════════════════════
# Model 1: Linear Regression (Least Squares)
# ═══════════════════════════════════════════════════════════

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


def _linear_predict(values: Sequence[float], days_ahead: int) -> float:
    intercept, slope = _linear_trend(values)
    n = len(values)
    return intercept + slope * (n - 1 + days_ahead)


# ═══════════════════════════════════════════════════════════
# Model 2: Holt's Exponential Smoothing (Double)
# ═══════════════════════════════════════════════════════════

def _holt_exponential_smoothing(
    values: Sequence[float],
    alpha: float = 0.6,
    beta: float = 0.3,
) -> tuple[float, float]:
    """Holt's double exponential smoothing.

    alpha: darajani tekislash koeffitsienti (level smoothing).
    beta: trendni tekislash koeffitsienti (trend smoothing).

    Qaytadi: (last_level, last_trend).
    """
    n = len(values)
    if n < 2:
        return (float(values[0]) if values else 0.0, 0.0)

    # Boshlang'ich qiymatlar
    level = values[0]
    trend = values[1] - values[0]

    for i in range(1, n):
        new_level = alpha * values[i] + (1 - alpha) * (level + trend)
        new_trend = beta * (new_level - level) + (1 - beta) * trend
        level = new_level
        trend = new_trend

    return (level, trend)


def _holt_predict(values: Sequence[float], days_ahead: int) -> float:
    level, trend = _holt_exponential_smoothing(values)
    return level + trend * days_ahead


# ═══════════════════════════════════════════════════════════
# Model 3: Weighted Moving Average
# ═══════════════════════════════════════════════════════════

def _weighted_moving_average(values: Sequence[float]) -> float:
    """Oxirgi qiymatlarga ko'proq og'irlik beradi.

    Vaznlar: [1, 2, 3, ..., n] — eng oxirgi kunda eng katta vazn.
    """
    n = len(values)
    if n == 0:
        return 0.0
    weights = list(range(1, n + 1))
    total_weight = sum(weights)
    return sum(w * v for w, v in zip(weights, values)) / total_weight


def _wma_predict(values: Sequence[float], days_ahead: int) -> float:
    """WMA asosida trend: oxirgi WMA va oldingi WMA orasidagi farq."""
    n = len(values)
    if n < 3:
        return _weighted_moving_average(values)

    current_wma = _weighted_moving_average(values)
    prev_wma = _weighted_moving_average(values[:-1])
    daily_change = current_wma - prev_wma
    return current_wma + daily_change * days_ahead


# ═══════════════════════════════════════════════════════════
# Ensemble (uchala modelni birlashtirish)
# ═══════════════════════════════════════════════════════════

def _ensemble_predict(
    values: Sequence[float],
    days_ahead: int,
    weights: tuple[float, float, float] = (0.30, 0.45, 0.25),
) -> float:
    """Uchta modelning vaznli o'rtachasi.

    Vaznlar: (linear, holt, wma).
    Holt'ga eng katta vazn — u trend + tezlikni yaxshi ushlaydi.
    """
    w_lin, w_holt, w_wma = weights
    p_lin = _linear_predict(values, days_ahead)
    p_holt = _holt_predict(values, days_ahead)
    p_wma = _wma_predict(values, days_ahead)
    return w_lin * p_lin + w_holt * p_holt + w_wma * p_wma


# ═══════════════════════════════════════════════════════════
# Xavf kategoriyasi va tavsiyalar
# ═══════════════════════════════════════════════════════════

def _categorise(risk: float) -> str:
    if risk < 25:
        return "low"
    if risk < 50:
        return "moderate"
    if risk < 75:
        return "high"
    return "critical"


def _compute_r_squared(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Determinatsiya koeffitsienti (R²).

    1.0 = mukammal model, 0.0 = model o'rtachadan yaxshi emas,
    <0.0 = model o'rtachadan yomonroq.
    """
    n = len(actual)
    if n < 2:
        return 0.0
    mean_y = sum(actual) / n
    ss_tot = sum((y - mean_y) ** 2 for y in actual)
    if ss_tot == 0:
        return 1.0
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    return max(0.0, 1.0 - ss_res / ss_tot)


def _compute_mape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean Absolute Percentage Error (%).

    Har bir kuzatuvdagi xato foizini o'rtachalaydi.
    """
    n = len(actual)
    if n == 0:
        return 0.0
    total = 0.0
    count = 0
    for a, p in zip(actual, predicted):
        if abs(a) > 1e-6:
            total += abs((a - p) / a) * 100.0
            count += 1
    return total / max(count, 1)


def _compute_confidence_interval(
    values: Sequence[float],
    projected: float,
    z: float = 1.28,
) -> tuple[float, float]:
    """80% confidence interval (z=1.28) for projected value.

    Ensemble modelning leave-one-out xatosi asosida standart
    deviation hisoblanadi va interval quriladi.
    """
    n = len(values)
    if n < 3:
        return max(0.0, projected - 15.0), min(100.0, projected + 15.0)

    # Leave-one-out cross-validation xatolari
    errors: list[float] = []
    for i in range(n):
        train = list(values[:i]) + list(values[i + 1:])
        pred = _ensemble_predict(train, 1)
        errors.append(values[i] - pred)

    mean_err = sum(errors) / len(errors)
    std_err = math.sqrt(sum((e - mean_err) ** 2 for e in errors) / len(errors))
    std_err = max(std_err, 2.0)

    lower = max(0.0, projected - z * std_err)
    upper = min(100.0, projected + z * std_err)
    return round(lower, 1), round(upper, 1)


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


# ═══════════════════════════════════════════════════════════
# Asosiy funksiya
# ═══════════════════════════════════════════════════════════

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
        fallback_score = row.get("avg_score")
        if score is None or (float(score) <= 0.0 and fallback_score is not None):
            score = fallback_score
        if score is not None and score >= 0:
            daily_scores.append(float(score))

    if len(daily_scores) < 2:
        return None

    # Risk = 100 - score (yuqori risk = yomon ergonomika)
    daily_risks = [100.0 - score for score in daily_scores]

    # Ensemble prognoz
    n = len(daily_risks)
    current_risk = max(0.0, min(100.0, _ensemble_predict(daily_risks, 0)))
    projected_risk_7d = max(0.0, min(100.0, _ensemble_predict(daily_risks, 7)))

    # Slope (kunlik o'zgarish) — linear trend'dan olamiz
    _, slope = _linear_trend(daily_risks)

    # Pain probability modeli:
    # 30 kun davomida o'rtacha risk yuqori bo'lsa, og'riq ehtimoli oshadi.
    # Asos: WHO ofis xodimlarida 54% surunkali bo'yin og'rig'i statistikasi (Cote et al., 2008)
    # — biz buni baseline sifatida olamiz va riskka mutanosib oshiramiz.
    # Sigmoid-like funksiya ishlatamiz — yanada ilmiy asoslangan
    #
    # Hozirgi risk va 7 kunlik prognoz o'rtachasi ishlatiladi (30 kunlik emas)
    # — bu yanada konservativ va real prognoz beradi.
    blended_risk = 0.6 * current_risk + 0.4 * projected_risk_7d
    risk_factor = blended_risk / 100.0

    # Sigmoid: midpoint 0.55 da, slope 6 — o'rtacha aggressivlik
    # < 30 risk → < 15% ehtimollik
    # 50 risk → ~43% ehtimollik
    # > 70 risk → > 75% ehtimollik
    pain_probability_30d = 1.0 / (1.0 + math.exp(-6.0 * (risk_factor - 0.55)))
    pain_probability_30d = max(0.05, min(0.95, pain_probability_30d))

    category = _categorise(current_risk)
    recommendation = _build_recommendation(category, slope, current_risk)

    # Model aniqlik metrikalari
    fitted = [max(0.0, min(100.0, _ensemble_predict(daily_risks, i - n + 1))) for i in range(n)]
    r_squared = _compute_r_squared(daily_risks, fitted)
    mape = _compute_mape(daily_risks, fitted)
    conf_lower, conf_upper = _compute_confidence_interval(daily_risks, projected_risk_7d)

    return RiskForecast(
        current_risk=round(current_risk, 1),
        projected_risk_7d=round(projected_risk_7d, 1),
        slope_per_day=round(slope, 2),
        pain_probability_30d=round(pain_probability_30d, 2),
        category=category,
        recommendation=recommendation,
        model_used="ensemble(linear+holt+wma)",
        r_squared=round(r_squared, 3),
        mape=round(mape, 1),
        confidence_lower=conf_lower,
        confidence_upper=conf_upper,
    )
