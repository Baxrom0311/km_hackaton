# PostureAI — To'liq Texnik Arxitektura

> **AI HEALTH 2026** Respublika Hakatoni  
> Sun'iy intellekt asosidagi ergonomik xavf monitoringi va prognozlash tizimi  
> Platform: Desktop (Windows / macOS / Linux) | Python 3.11+ | PySide6 GUI

---

## 1. Tizim Umumiy Ko'rinishi

PostureAI — kompyuter webcami orqali foydalanuvchining o'tirish pozitsiyasini real vaqtda tahlil qiluvchi, ergonomik xavfni baholovchi va kelajakdagi mushak-skelet og'rig'ini bashorat qiluvchi to'liq grafik interfeysli desktop ilova.

### Asosiy Funksiyalar

| # | Funksiya | Modul | Ilmiy Asos |
|---|---|---|---|
| 1 | Real-time poza aniqlash | `vision/detector.py` | BlazePose Heavy, CVPR 2020 |
| 2 | Multi-signal ergonomik ball | `core/ergonomics.py` | Posture + Sit + Eye + Gaze |
| 3 | Temporal filter (false alarm -95%) | `core/filter.py` | Telban-Gonzalez, 2019 |
| 4 | Ensemble prediktiv prognoz | `core/forecast.py` | Linear + Holt + WMA |
| 5 | Shaxsiy mashq tavsiyalari | `core/exercises.py` | Page, IJSPT 2012 |
| 6 | AI kalibrovka (shaxsiy profil) | `vision/detector.py` | Individual baseline |
| 7 | Ekran xiraytirish (Nudge) | `os_utils/dimmer.py` | Thaler & Sunstein, 2008 |
| 8 | Ovozli ogohlantirish | `os_utils/audio_helper.py` | Keshlangan audio + OS TTS fallback |

---

## 2. Arxitektura Diagrammasi

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INPUT LAYER                                │
│   Webcam (720p/1080p) → OpenCV VideoCapture → 10 FPS kadrlar       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ BGR frame (numpy array)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AI POSE ESTIMATION LAYER                         │
│                                                                     │
│   MediaPipe BlazePose Heavy → 33 ta 3D landmark (96.4% PCKh@0.5)  │
│   ├── Visibility check (≥ 0.5)                                     │
│   ├── Camera distance check (yelka masofa)                         │
│   └── 5 ta asosiy landmark: burun(0), quloqlar(7,8), yelkalar(11,12) │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ 33 ta (x, y, z, visibility) nuqta
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  MULTI-SIGNAL ANALYSIS LAYER                        │
│                                                                     │
│   1. Camera view        : XY roll + XZ yaw + YZ pitch baseline     │
│   2. XY roll            : camera-compensated bosh qiyshayishi      │
│   3. XZ yaw             : camera-compensated bo'yin burilishi      │
│   4. YZ pitch           : oldinga/orqaga engashish                 │
│   5. Eye strain         : face-camera distance (sigmoid risk)      │
│   6. Sit duration       : continuous sit tracking (25 min alert)   │
│   7. Eye gaze tracking  : 20-20-20 rule (20 min continuous)       │
│                                                                     │
│   → Posture Score (0-100) + Ergonomic Score (0-100)                │
│   → Issues list: ["Boshingizni ko'taring!", ...]                   │
└───────────┬──────────────────────┬──────────────────────────────────┘
            │ har kadr             │ 70%+ bad kadrlar
            ▼                      ▼
┌────────────────────┐   ┌────────────────────────────────────────────┐
│  STATISTIKA        │   │  TEMPORAL FILTER + ALERT SYSTEM            │
│                    │   │                                            │
│  SQLite app-data DB│   │  Sliding window: 90 frame, 70% threshold  │
│  ├── sessions      │   │  Cooldown: 60 sekund                      │
│  ├── posture_logs  │   │  ↓                                        │
│  └── alerts        │   │  ├── OS Notification (cross-platform)     │
│                    │   │  ├── O'zbek tilidagi ovozli alert          │
│  → Haftalik summary│   │  ├── Ekran xiraytirish (Nudge theory)     │
│  → Forecast input  │   │  └── Tray icon rangi (yashil/qizil)      │
└────────┬───────────┘   └────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  PREDICTIVE FORECAST LAYER                          │
│                                                                     │
│  Ensemble Model (3 ta statistik model):                            │
│  ├── Linear Regression (30%) — trend yo'nalishi                    │
│  ├── Holt Double Exp. Smoothing (45%) — trend + tezlik             │
│  └── Weighted Moving Average (25%) — oxirgi kunlar og'irligi       │
│                                                                     │
│  Pain Probability = sigmoid(6 * (blended_risk/100 - 0.55))        │
│  → 30 kunlik og'riq ehtimoli (0-95%)                              │
│  → Xavf kategoriyasi: low / moderate / high / critical             │
│  → Shaxsiy tavsiya + Mashq rejasi                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Fayl Tuzilmasi (src/posture_ai/)

```
src/posture_ai/
│
├── main.py                    # Kirish nuqtasi — PySide6 GUI ishga tushirish
├── __init__.py
│
├── core/                      # Biznes logika
│   ├── config.py              # Pydantic AppConfig — barcha sozlamalar
│   ├── filter.py              # Temporal sliding window filter
│   ├── forecast.py            # Ensemble prediktiv model (LR + Holt + WMA)
│   ├── ergonomics.py          # Ergonomik ball, sit tracker, eye gaze, 20-20-20
│   └── exercises.py           # Mashq tavsiyalari bazasi va tavsiya algoritmi
│
├── vision/                    # AI va kompyuter ko'rish
│   ├── detector.py            # PoseDetector + MediaPipe + burchak hisoblash
│   ├── camera_worker.py       # QThread — asinxron kamera ishchi thread
│   └── visual.py              # Debug/demo vizual rejim (overlay + screenshot)
│
├── database/                  # Ma'lumotlar saqlash
│   └── storage.py             # SQLite CRUD — sessions, logs, alerts, stats
│
├── gui/                       # Grafik interfeys (PySide6)
│   ├── main_window.py         # Asosiy oyna + sidebar + tray icon
│   ├── styles.py              # Deep Navy glassmorphism CSS tema
│   ├── tray.py                # System tray (pystray fallback)
│   └── pages/
│       ├── dashboard.py       # Asosiy panel — score, kamera, trend, mashqlar
│       ├── calibration.py     # AI kalibrovka sahifasi
│       └── settings.py        # Sozlamalar sahifasi
│
└── os_utils/                  # OS-specific xizmatlar
    ├── notifier.py            # Cross-platform bildirishnoma (Win/Mac/Linux)
    ├── dimmer.py              # Ekran xiraytirish (gamma API)
    └── audio_helper.py        # Cache + OS TTS fallback ogohlantirishlar
```

---

## 4. Texnik Stack

| Komponent | Texnologiya | Versiya | Maqsad |
|---|---|---|---|
| AI Model | MediaPipe BlazePose Heavy | 0.10+ | 33 ta 3D landmark, 96.4% aniqlik |
| Kamera | OpenCV | 4.8+ | Kadr olish, vizualizatsiya |
| GUI | PySide6 (Qt for Python) | 6.6+ | Premium desktop interfeys |
| Database | SQLite3 | stdlib | Sessiyalar, loglar, alertlar |
| Config | Pydantic v2 | 2.4+ | Tipli config validatsiya |
| Logging | Loguru | 0.7+ | Rotatsiyali log fayllar |
| Audio | gTTS cache + OS TTS | latest | Lokal/cached ovozli alertlar |
| Packaging | PyInstaller | latest | .exe / .app qadoqlash |

---

## 5. Ma'lumotlar Oqimi (Data Flow)

### 5.1. Real-time Loop (CameraWorker thread)

```
har 100ms (10 FPS):
  1. frame = camera.read()
  2. landmarks = MediaPipe.detect(frame)
  3. camera_view = estimate_view(landmarks)        → kamera/torso XY, XZ, YZ baseline
  4. metrics = measure_posture(landmarks)          → compensated XY, XZ, YZ, shoulder, lean
  5. face_distance = estimate_distance(landmarks)   → ko'z masofasi
  6. posture_score = calculate_score(metrics)        → 0-100 ball
  7. ergonomic_score = compute_ergonomic(            → 0-100 ball
       posture_score, sit_time, eye_distance, gaze_time)
  8. temporal_filter.update(status == "bad")
     → if triggered: emit alert_signal → notification + audio + dimmer
  9. emit metrics_signal → dashboard real-time yangilash
```

### 5.2. Statistika Yozish (har 60 sekund)

```
  1. storage.log_posture(session_id, last_result)
  2. SQLite: INSERT INTO posture_logs (timestamp, status, angles, scores)
```

### 5.3. Predictive Forecast (Dashboard ochilganda)

```
  1. weekly = storage.get_weekly_summary()      → 7 kunlik o'rtachalar
  2. daily_risks = [100 - score for score in weekly]
  3. ensemble_predict(daily_risks, days_ahead)   → 3 model birlashtiriladi
  4. pain_prob = sigmoid(6 * (blended_risk/100 - 0.55)) → og'riq ehtimoli
  5. recommendation = build_recommendation(category, slope)
  6. exercises = recommend_exercises(frequent_issues)
```

---

## 6. Ergonomic Score Formulasi

```python
Ergonomic Score = Posture Score
                  - Sit Duration Penalty (max 25%)
                  - Eye Strain Penalty (max 15%)
                  - Gaze Duration Penalty (max 10%)
```

| Komponent | Vazn | 0% penalti | 100% penalti |
|---|---|---|---|
| Posture Score | Base (100) | Yaxshi o'tirish | Barcha mezonlar buzilgan |
| Sit Duration | 25% | ≤ 25 daqiqa | ≥ 90 daqiqa uzluksiz |
| Eye Strain | 15% | Masofa ≥ 50 sm | Masofa ≤ 30 sm |
| Gaze Duration | 10% | ≤ 20 daqiqa | ≥ 60 daqiqa uzluksiz |

---

## 7. Ensemble Forecast Modeli

### Model Arxitekturasi

| # | Model | Vazn | Formulasi | Maqsad |
|---|---|---|---|---|
| 1 | Linear Regression | 30% | y = kx + b (least squares) | Umumiy trend |
| 2 | Holt Exp. Smoothing | 45% | L_t = α·y_t + (1-α)·(L_{t-1}+T_{t-1}) | Trend + tezlik |
| 3 | Weighted Moving Avg | 25% | Σ(w_i · y_i) / Σ(w_i), w = [1,2,...,n] | Oxirgi kunlar |

### Og'riq Ehtimoli

```
blended_risk = 0.6 * current_risk + 0.4 * projected_risk_7d
P(pain, 30d) = 1 / (1 + e^(-6 * (blended_risk/100 - 0.55)))
```

Sigmoid tanlangan sabab:
- Past riskda sekin o'sadi (false alarm kamaytiradi)
- Yuqori riskda tez o'sadi (haqiqiy xavfni ko'rsatadi)
- Biologik/epidemiologik modellashtirish uchun standart

Baseline: Cote et al. (2008) — ofis ishchilarida 54% surunkali bo'yin og'rig'i.

---

## 8. AI Kalibrovka Jarayoni

```
1. Foydalanuvchi "Kalibrovka" sahifasini ochadi
2. 12 soniya davomida to'g'ri o'tiradi (kamera oldida)
3. Tizim ≥25 ta posture namunasi yig'adi
4. Median burchaklar hisoblanadi → individual baseline
5. Threshold'lar baseline ga nisbatan hisoblanadi:
   - head_threshold = max(baseline + 8°, 18°)
   - shoulder_threshold = max(baseline + 0.02, 0.03)
   - forward_threshold = min(baseline - 0.12, -0.08)
6. Shaxsiy profil app-data ichidagi `config.json` ga saqlanadi
```

---

## 9. Tizim Talablari

| Parametr | Minimal | Tavsiya |
|---|---|---|
| Python | 3.10+ | 3.11+ |
| RAM | 256 MB | 512 MB |
| CPU | Dual-core | Quad-core |
| OS | Win10 / macOS 12 / Ubuntu 20.04 | Eng oxirgi versiya |
| Webcam | 720p | 1080p |
| Disk | 100 MB | 200 MB |

---

## 10. Ilmiy Manbalar

To'liq ro'yxat uchun qarang: **[REFERENCES.md](REFERENCES.md)**

Asosiy manbalar:
1. Bazarevsky et al. "BlazePose." CVPR 2020 — AI model arxitekturasi
2. Hansraj. Surg Technol Int, 2014 — umurtqa bosimi threshold'lari
3. Cote et al. Eur Spine J, 2008 — epidemiologik baseline
4. Thaler & Sunstein. "Nudge", 2008 — xulq-atvor o'zgartirish nazariyasi
5. Page. IJSPT, 2012 — cho'zilish mashqlari ilmiy asosi

---

*Hujjat versiyasi: 2.0 | PostureAI — AI HEALTH 2026*
