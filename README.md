# AI HEALTH - 2026: PostureAI

<div align="center">
  <h3>Sun'iy intellekt asosidagi ergonomik xavf monitoringi va prognozlash tizimi</h3>
  
  [![Hackathon](https://img.shields.io/badge/AI_HEALTH-2026-00f5d4?style=for-the-badge)](rules.txt)
  [![MVP Validated](https://img.shields.io/badge/MVP-100%25_TESTED-7b61ff?style=for-the-badge)](TEST_REPORT.md)
  [![References](https://img.shields.io/badge/ILMIY_ASOS-15%2B_MANBA-ff9f43?style=for-the-badge)](REFERENCES.md)
</div>

---

## Loyiha Haqida

PostureAI — webcam orqali foydalanuvchining o'tirish pozitsiyasini real vaqtda tahlil qiluvchi, **6 ta signal** asosida ergonomik xavfni baholovchi va **ensemble ML modeli** yordamida kelajakdagi mushak-skelet og'rig'ini bashorat qiluvchi profilaktik tizim.

### Asosiy Imkoniyatlar

| # | Funksiya | Texnologiya |
|---|---|---|
| 1 | Real-time poza aniqlash (33 landmark) | MediaPipe BlazePose Heavy (96.4% aniqlik) |
| 2 | Multi-signal ergonomik ball | Posture + Sit duration + Eye strain + Gaze tracking |
| 3 | Prediktiv 30 kunlik og'riq prognozi | Ensemble: Linear + Holt Exp.Smoothing + WMA |
| 4 | Shaxsiy mashq tavsiyalari | Muammoga qarab ilmiy asoslangan cho'zilish mashqlari |
| 5 | AI kalibrovka (shaxsiy profil) | 12 sek to'g'ri o'tirish → individual baseline |
| 6 | Ekran xiraytirish (Nudge) | Gamma API — noto'g'ri posture'da ekran xiraylashadi |
| 7 | O'zbek tilidagi ovozli ogohlantirish | gTTS + pygame (to'liq offlayn) |
| 8 | Premium GUI Dashboard | PySide6 — Deep Navy glassmorphism |

### Texnik Stack
- **AI Backend**: Python 3.11, MediaPipe BlazePose Heavy, OpenCV
- **ML Forecast**: Ensemble (Linear Regression + Holt Double Exp. Smoothing + Weighted Moving Average) + Sigmoid pain probability
- **GUI**: PySide6 (Qt for Python) — Premium Dark Theme
- **Database**: SQLite — sessions, posture logs, alerts
- **Config**: Pydantic v2 — tipli validatsiya
- **Audio**: gTTS + pygame — O'zbek tilidagi TTS

---

## Ishga Tushirish

```bash
# 1. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 2. (Ixtiyoriy) Demo uchun 7 kunlik mock ma'lumot yaratish
python generate_mock_data.py

# 3. To'laqonli grafik interfeysli oynani ochish
python src/posture_ai/main.py
```

### Dasturni Qadoqlash (.exe / .app)
```bash
pip install pyinstaller
python build.py
```
*Natija `dist/PostureAI` papkasida mustaqil dastur sifatida hosil bo'ladi.*

---

## Baholash Mezonlari Bo'yicha Hujjatlar

Hakamlar hay'ati diqqatiga — loyiha to'liq **5.2.3 Baholash mezonlari (100 ball)** ga asoslangan:

| # | Mezon | Ball | Hujjat |
|---|---|---|---|
| 1 | **Dolzarblik va amalga oshirish** | 20 | [PITCH.md](PITCH.md) — Slayd 2: WHO/PubMed statistikasi |
| 2 | **Innovatsionlik va yangilik** | 25 | [Arxitektura.md](Arxitektura.md) — Ensemble ML, 6-signalli ergonomika |
| 3 | **MVP mavjudligi va sinovlar** | 25 | [TEST_REPORT.md](TEST_REPORT.md) — 5 ishtirokchi, 3 kun, p<0.01 |
| 4 | **Ilmiy asoslanganlik** | 10 | [REFERENCES.md](REFERENCES.md) — 15+ ilmiy manba, har bir threshold asoslangan |
| 5 | **Savol-javob** | 15 | [PITCH.md](PITCH.md) — 10+ texnik/klinik savol-javob tayyor |
| 6 | **Prezentatsiya sifati** | 10 | [PITCH.md](PITCH.md) — 9 slayd, 6 daqiqa nutq, landing page |

---

## Sinov Natijalari (Qisqacha)

| Ko'rsatkich | Oldin | Keyin | O'zgarish |
|:---|:---:|:---:|:---:|
| To'g'ri o'tirish foizi | 45% | 73% | **+28%** |
| Subyektiv og'riq (0-10) | 6.2 | 3.8 | **-2.4** |
| Max uzluksiz o'tirish | 120 daq | 42 daq | **-78 daq** |
| False alarm rate | — | 4.7% | — |

*To'liq natijalar: [TEST_REPORT.md](TEST_REPORT.md)*

---
*PostureAI — AI Health 2026 Respublika Hakatoni*
