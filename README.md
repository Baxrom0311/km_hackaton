# PostureAI Desktop MVP

`PostureAI` webcam orqali foydalanuvchining o'tirish holatini tahlil qiladi, noto'g'ri posture uzoq davom etsa ogohlantiradi, ekranni xiraytiradi, ko'z zo'riqishi va uzluksiz o'tirish vaqtini kuzatadi, kelajakdagi og'riq xavfini bashorat qiladi.

## Asosiy funksiyalar

| Funksiya | Tavsif |
|---|---|
| **Posture Detection** | Bosh burchagi, yelka simmetriyasi, oldinga engashish — real vaqtda |
| **Eye Strain Monitoring** | Yuz-kamera masofasi orqali ko'z zo'riqishi xavfi |
| **20-20-20 Eye Gaze** | 20 daqiqa uzluksiz ekranga qarash → eslatma |
| **Smart Break Reminder** | 25+ daqiqa uzluksiz o'tirish → tanaffus eslatmasi |
| **Screen Dimming** | Yomon posture → ekran xira bo'ladi, yaxshilansa tiklanadi |
| **Predictive Forecast** | 7 kunlik tarixdan 30 kunlik og'riq ehtimolini bashorat qiladi |
| **Ergonomic Score** | 5 ta signal birlashtirilgan 0–100 ball |

## Fayl tuzilmasi

```
main.py          — CLI va ishga tushirish oqimi
detector.py      — MediaPipe pose detection va posture tahlili
ergonomics.py    — SitDurationTracker, EyeGazeTracker, ergonomic score
filter.py        — sliding-window temporal filter
notifier.py      — cross-platform notification (macOS/Windows/Linux)
dimmer.py        — ekran xiraytirish (macOS/Windows/Linux)
storage.py       — SQLite session, log, alert saqlash
tray.py          — system tray + console fallback
visual.py        — OpenCV jonli oyna (debug/demo)
forecast.py      — 7 kunlik trend + 30 kunlik og'riq prognozi
config.json      — sozlamalar
models/          — MediaPipe model fayli
tests/           — unit testlar (43 ta)
```

---

## macOS da ishga tushirish

### Talab

- Python 3.11 (MediaPipe eng barqaror shu versiyada)
- Webcam (ichki yoki tashqi)

### O'rnatish

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Ishga tushirish

```bash
python main.py              # tray rejim (menubar)
python main.py --console    # terminal rejim
python main.py --visual     # kamera oynasi (demo/sinov)
python main.py --doctor     # diagnostika
python main.py --calibrate  # shaxsiy kalibrovka
python main.py --stats      # bugungi + haftalik statistika + forecast
```

---

## Windows da ishga tushirish

### Talab

- **Python 3.11** (boshqa versiyalarda MediaPipe ishlamasligi mumkin)
- Webcam (ichki yoki USB)

### 1-qadam: Python 3.11 o'rnatish

1. [python.org/downloads](https://www.python.org/downloads/release/python-3119/) dan Python 3.11 yuklab oling
2. O'rnatish vaqtida **"Add Python to PATH"** ni belgilang
3. **"Install for all users"** tanlang

Tekshirish:
```cmd
python --version
```
`Python 3.11.x` chiqishi kerak.

### 2-qadam: Loyihani clone/yuklab olish

```cmd
cd %USERPROFILE%\Desktop
git clone <repo-url> PostureAI
cd PostureAI
```

Yoki ZIP yuklab olib, Desktop ga chiqaring.

### 3-qadam: Virtual environment

```cmd
python -m venv .venv
.venv\Scripts\activate
```

> Agar PowerShell ishlatayotgan bo'lsangiz va xatolik chiqsa:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> .venv\Scripts\Activate.ps1
> ```

### 4-qadam: Dependencies o'rnatish

```cmd
pip install -r requirements.txt
```

> **Diqqat:** `pyobjc-framework-Quartz` faqat macOS da o'rnatiladi (Windows da avtomatik o'tkazib yuboriladi). `win10toast` faqat Windows da o'rnatiladi.

### 5-qadam: Model fayli

`models/` papkasida `pose_landmarker_heavy.task` fayli bo'lishi kerak. Agar yo'q bo'lsa:

1. [MediaPipe Pose Landmarker](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker#models) sahifasidan **Heavy** modelni yuklab oling
2. `models/pose_landmarker_heavy.task` sifatida saqlang

### 6-qadam: Ishga tushirish

```cmd
python main.py --doctor
```

Hammasi `ok` bo'lsa:

```cmd
python main.py --visual
```

### Windows uchun barcha rejimlar

```cmd
:: Tray rejim (system tray ikonka)
python main.py

:: Terminal rejim (loglar ko'rinadi)
python main.py --console

:: Visual rejim (kamera oynasi — demo/sinov uchun)
python main.py --visual

:: Chiziqlarsiz visual
python main.py --visual -d

:: Shaxsiy kalibrovka (12 sek to'g'ri o'tirib turing)
python main.py --calibrate

:: Diagnostika (kamera, model, dependencies)
python main.py --doctor

:: Statistika va prognoz
python main.py --stats
```

### Windows muammolar va yechimlari

| Muammo | Yechim |
|---|---|
| `pip install mediapipe` xatolik | Python 3.11 o'rnatilganini tekshiring (`python --version`) |
| Kamera ochilmaydi | Settings → Privacy → Camera → Allow apps to access camera |
| Notification chiqmaydi | Settings → System → Notifications → Python/Terminal uchun yoqilgan |
| `pystray` ishlamaydi | `python main.py --console` yoki `--visual` ishlatib ko'ring |
| Ekran dim ishlamaydi | Gamma Ramp qo'llab-quvvatlanmagan driver; ilovaga ta'sir qilmaydi |
| `ModuleNotFoundError: win10toast` | `pip install win10toast` |

---

## Visual rejim hotkeylar

| Tugma | Funksiya |
|---|---|
| **D** | Debug chiziqlar (landmark/skelet) ON/OFF |
| **I** | Info panel (scorelar, burchaklar) ON/OFF |
| **N** | Notificationlar ON/OFF |
| **H** | Help panel ON/OFF |
| **Space** | Pause/Resume |
| **S** | Screenshot (`screenshots/` papkasiga saqlaydi) |
| **F** | Fullscreen rejim |
| **Q / ESC** | Chiqish |

## Kalibrovka

```bash
python main.py --calibrate
```

10–12 soniya kameraga to'g'ri posture bilan o'tirib turing. Shaxsiy bosh burchagi, yelka simmetriyasi va engashish thresholdlari `config.json` ga yoziladi.

## Testlar

```bash
python -m unittest discover -s tests -v
```

43 ta test, barcha platformalarda ishlaydi (macOS, Windows, Linux).

## Texnik stack

- **Python 3.11** — asosiy til
- **MediaPipe BlazePose Heavy** — 33 ta body landmark (96.4% PCKh@0.5)
- **OpenCV** — kamera va vizualizatsiya
- **SQLite** — lokal ma'lumotlar bazasi
- **pystray** — system tray UI
- **Quartz** (macOS) / **GDI32** (Windows) / **xrandr** (Linux) — ekran dimming
- **plyer** / **win10toast** — cross-platform notification
