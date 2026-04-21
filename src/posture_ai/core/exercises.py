"""Shaxsiy cho'zilish mashqlari tavsiya moduli.

Foydalanuvchining eng ko'p uchraydigan muammolariga qarab
maxsus mashqlar tavsiya qiladi. Ilmiy asos:
  - Page P, "Current concepts in muscle stretching for exercise", Int J Sports Phys Ther, 2012
  - Ylinen J, "Stretching therapy for sport and manual therapies", Churchill Livingstone, 2008
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(slots=True)
class Exercise:
    """Bitta cho'zilish mashqi."""
    name: str
    target: str          # qaysi mushak guruhi
    description: str     # qanday bajarish
    duration_sec: int    # davomiyligi
    difficulty: str      # "oson" / "o'rta"
    benefit: str         # qanday foyda


# Mashqlar bazasi — muammoga qarab guruhlangan
EXERCISES_DB: dict[str, list[Exercise]] = {
    "head_tilt": [
        Exercise(
            name="Bo'yin cho'zilishi (Chin Tuck)",
            target="Bo'yin oldingi mushaklari",
            description="To'g'ri o'tiring. Iyagingizni sekin orqaga torting (ikkilanmasdan). "
                        "10 soniya ushlab turing. 5 marta takrorlang.",
            duration_sec=60,
            difficulty="oson",
            benefit="Bo'yin oldingi mushaklarini mustahkamlaydi, bosh oldinga engashishni kamaytiradi.",
        ),
        Exercise(
            name="Trapetsiya cho'zilishi",
            target="Trapetsiya mushaklari (bo'yin yon)",
            description="O'ng qo'lingiz bilan boshingizning chap tomonini sekin o'ng tomonga eging. "
                        "15 soniya ushlab turing. Har tomoniga 3 marta.",
            duration_sec=90,
            difficulty="oson",
            benefit="Bo'yin yon mushaklaridagi qotishlikni yo'qotadi.",
        ),
    ],
    "shoulder_diff": [
        Exercise(
            name="Yelka aylantirish",
            target="Deltoid va trapetsiya mushaklari",
            description="Ikkala yelkangizni bir vaqtda oldinba orqaga aylantiring. "
                        "10 marta oldinga, 10 marta orqaga.",
            duration_sec=40,
            difficulty="oson",
            benefit="Yelka simmetriyasini tiklaydi, qon aylanishni yaxshilaydi.",
        ),
        Exercise(
            name="Kupalda qo'l cho'zilishi (Doorway Stretch)",
            target="Ko'krak va yelka oldingi mushaklari",
            description="Eshik romiga ikkala qo'lingizni qo'yib, sekin oldinga egilning. "
                        "20 soniya ushlab turing. 3 marta takrorlang.",
            duration_sec=60,
            difficulty="o'rta",
            benefit="Yelkalar orasidagi nosimmetriyani tuzatadi, ko'krak mushaklarini ochadi.",
        ),
    ],
    "forward_lean": [
        Exercise(
            name="Ko'krak ochish (Chest Opener)",
            target="Ko'krak va umurtqa pog'onasi",
            description="Qo'llaringizni orqangizda birlashtiring va sekin yuqoriga ko'taring. "
                        "Ko'krak ochilguncha ushlab turing — 15 soniya. 5 marta.",
            duration_sec=75,
            difficulty="oson",
            benefit="Oldinga engashish odatini tuzatadi, umurtqa holatini yaxshilaydi.",
        ),
        Exercise(
            name="Mushuk-sigir mashqi (Cat-Cow)",
            target="Umurtqa pog'onasi bo'ylab barcha mushaklar",
            description="To'rt oyoqda turing. Nafas olib orqangizni pastga eging (sigir), "
                        "nafas chiqarib yuqoriga qaytaring (mushuk). 10 marta.",
            duration_sec=60,
            difficulty="o'rta",
            benefit="Umurtqa egiluvchanligini oshiradi, surunkali og'riqni kamaytiradi.",
        ),
    ],
    "eye_strain": [
        Exercise(
            name="20-20-20 qoidasi",
            target="Ko'z mushaklari",
            description="20 daqiqa ishlangandan so'ng, 20 soniya davomida 6 metr (20 fut) "
                        "uzoqlikdagi biror narsaga qarang.",
            duration_sec=20,
            difficulty="oson",
            benefit="Ko'z charchog'ini 40-60% ga kamaytiradi (AAO tavsiyasi).",
        ),
        Exercise(
            name="Ko'z aylantirish",
            target="Ko'z tashqi mushaklari",
            description="Ko'zlaringizni soat yo'nalishida 5 marta, soatga teskari 5 marta aylantiring. "
                        "Keyin 10 soniya ko'zingizni yumib dam oling.",
            duration_sec=30,
            difficulty="oson",
            benefit="Ko'z mushaklarini bo'shashtiradi, Digital Eye Strain ni kamaytiradi.",
        ),
    ],
    "sit_duration": [
        Exercise(
            name="O'rningizdan turish + cho'zilish",
            target="Butun tana",
            description="O'rningizdan turib, qo'llaringizni tepaga cho'zing. "
                        "Panjalaringizda 5 soniya turing. 3 marta takrorlang.",
            duration_sec=30,
            difficulty="oson",
            benefit="Qon aylanishni tiklab, mushak qotishligini yo'qotadi.",
        ),
        Exercise(
            name="Bel cho'zilishi (Standing Hamstring Stretch)",
            target="Orqa son va bel mushaklari",
            description="Turib, bir oyoq'ingizni oldinga cho'zing (tizzani bukmasdan). "
                        "Sekin oldinga egilib 15 soniya ushlab turing. Har oyoqqa 3 marta.",
            duration_sec=90,
            difficulty="o'rta",
            benefit="Uzoq o'tirishdan qotib qolgan bel va son mushaklarini bo'shashtiradi.",
        ),
    ],
    "lean_back": [
        Exercise(
            name="Tana oldinga cho'zilish",
            target="Orqa va bel mushaklari",
            description="O'tirib, qo'llaringizni oldinga cho'zing va sekin oldinga egilib "
                        "15 soniya ushlab turing. 3 marta takrorlang.",
            duration_sec=60,
            difficulty="oson",
            benefit="Orqa mushaklarni faollashtiradi, orqaga yotish odatini tuzatadi.",
        ),
        Exercise(
            name="Plank mashqi (30 sek)",
            target="Core mushaklar (qorin + orqa)",
            description="Tirsakka suyanib plank holatida 30 soniya turing. "
                        "Tanangiz to'g'ri chiziqda bo'lsin. 2 marta takrorlang.",
            duration_sec=90,
            difficulty="o'rta",
            benefit="Core mushaklarni mustahkamlaydi, to'g'ri o'tirishni osonlashtiradi.",
        ),
    ],
    "neck_rotation": [
        Exercise(
            name="Bo'yin aylantirish",
            target="Bo'yin mushaklari (barcha yo'nalishlar)",
            description="Boshingizni sekin soat yo'nalishida 5 marta, keyin teskari yo'nalishda "
                        "5 marta aylantiring. Har bir aylanishda 3 soniya.",
            duration_sec=30,
            difficulty="oson",
            benefit="Bo'yin mushaklaridagi qotishlikni yo'qotadi, burilish diapazonini yaxshilaydi.",
        ),
        Exercise(
            name="Bo'yin chapga-o'ngga burish",
            target="Sternocleidomastoid mushak",
            description="Boshingizni sekin chapga burib 10 soniya ushlab turing, keyin "
                        "o'ngga burib 10 soniya. Har tomoniga 3 marta.",
            duration_sec=60,
            difficulty="oson",
            benefit="Bo'yin burilish odatini tuzatadi, mushak muvozanatini tiklaydi.",
        ),
    ],
    "lateral_tilt": [
        Exercise(
            name="Bosh yon cho'zilish",
            target="Scalene va trapetsiya mushaklari",
            description="O'ng qo'lingiz bilan boshingizni sekin o'ng tomonga eging. "
                        "15 soniya ushlab turing. Har tomoniga 3 marta.",
            duration_sec=90,
            difficulty="oson",
            benefit="Bosh qiyshayish odatini tuzatadi, bo'yin yon mushaklarini cho'zadi.",
        ),
    ],
    "slouch": [
        Exercise(
            name="Yelka tortish (Scapular Retraction)",
            target="Romboid va o'rta trapetsiya mushaklari",
            description="Yelkalaringizni orqaga tortib birlashtiring (kuraklar bir-biriga yaqinlashsin). "
                        "10 soniya ushlab turing. 8 marta takrorlang.",
            duration_sec=80,
            difficulty="oson",
            benefit="Yelkalar bukilishini tuzatadi, ko'krak mushaklarini ochadi.",
        ),
        Exercise(
            name="Devor oldida turib yelka cho'zilish",
            target="Ko'krak va yelka oldingi mushaklari",
            description="Devorga orqangiz bilan turing. Qo'llaringizni yon tomonga 90° ochib "
                        "devorga tegizing. 20 soniya ushlab turing. 3 marta.",
            duration_sec=60,
            difficulty="o'rta",
            benefit="Rounded shoulders ni tuzatadi, to'g'ri holat uchun mushaklarni o'rgatadi.",
        ),
    ],
}

# Muammo kalitlari → mashq guruhi mapping
_ISSUE_TO_GROUP: dict[str, str] = {
    "Boshingizni ko'taring!": "head_tilt",
    "Yelkalaringizni tekislang!": "shoulder_diff",
    "Oldinga engashmang!": "forward_lean",
    "Orqaga yotmang!": "lean_back",
    "Bo'yningizni to'g'rilang!": "neck_rotation",
    "Boshingiz qiyshaygan!": "lateral_tilt",
    "Yelkalaringizni oching!": "slouch",
    "Ekranga yaqin!": "eye_strain",
    "Ekrandan juda uzoqsiz!": "eye_strain",
    "Ekranga juda yaqinsiz!": "eye_strain",
    "20-20-20!": "eye_strain",
    "Tanaffus qiling!": "sit_duration",
}


def recommend_exercises(
    frequent_issues: Sequence[tuple[str, int]],
    max_exercises: int = 4,
) -> list[Exercise]:
    """Eng ko'p uchraydigan muammolarga asoslangan mashq tavsiyalari.

    Args:
        frequent_issues: [(issue_text, count), ...] — kamayish tartibida.
        max_exercises: Maksimal mashqlar soni.

    Returns:
        Tavsiya etilgan mashqlar ro'yxati (takrorlanmasdan).
    """
    seen_names: set[str] = set()
    result: list[Exercise] = []

    for issue_text, _count in frequent_issues:
        group = _ISSUE_TO_GROUP.get(issue_text)
        if not group or group not in EXERCISES_DB:
            continue

        for ex in EXERCISES_DB[group]:
            if ex.name not in seen_names and len(result) < max_exercises:
                result.append(ex)
                seen_names.add(ex.name)

    # Agar hali joy bo'lsa, umumiy cho'zilish mashqlarini qo'shamiz
    if len(result) < max_exercises:
        for ex in EXERCISES_DB.get("sit_duration", []):
            if ex.name not in seen_names and len(result) < max_exercises:
                result.append(ex)
                seen_names.add(ex.name)

    return result


def get_daily_routine(issues_today: Sequence[str]) -> list[Exercise]:
    """Bugungi muammolar asosida oddiy mashq rejasi."""
    # Muammolarni sanalanganga aylantirish
    from collections import Counter
    counts = Counter(issues_today)
    frequent = counts.most_common()
    return recommend_exercises(frequent, max_exercises=4)
