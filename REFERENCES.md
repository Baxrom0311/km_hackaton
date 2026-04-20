# Ilmiy Manbalar va Klinik Asoslar

## PostureAI — AI HEALTH 2026

Ushbu hujjat loyihada foydalanilgan barcha ilmiy manbalar, klinik threshold'lar va algoritmik qarorlarning asoslarini tavsiflaydi.

---

## 1. Muammo Dolzarbligi (Epidemiologik Ma'lumotlar)

| Statistika | Manba |
|---|---|
| Har yili ~30% global aholida bo'yin og'rig'i kuzatiladi | Fejer R, et al. "The epidemiology of neck pain." *BMC Musculoskelet Disord*, 2022; 23:361 |
| 0.5–5.2% o'smirlarda idiopathic skolioz | Konieczny MR, et al. "Epidemiology of adolescent idiopathic scoliosis." *J Child Orthop*, 2013; 7(1):3–9 |
| >4 soat/kun o'tirish — mushak-skelet kasalliklari xavfini oshiradi | Park JH, et al. "Sedentary lifestyle: overview of updated evidence." *Korean J Fam Med*, 2020; 41(6):365–373 |
| 50–90% ekran oldida ishlovchilarda Digital Eye Strain (DES) | Sheppard AL, Wolffsohn JS. "Digital eye strain: prevalence, measurement, and amelioration." *BMJ Open Ophthalmol*, 2018; 3(1):e000146 |
| 54% ofis ishchilarida surunkali bo'yin og'rig'i | Cote P, et al. "The burden and determinants of neck pain." *Eur Spine J*, 2008; 17(Suppl 1):60–74 |

---

## 2. AI Model va Poza Aniqlash

### MediaPipe BlazePose

| Parametr | Qiymat | Manba |
|---|---|---|
| Model | BlazePose Heavy (33 landmark) | Bazarevsky V, et al. "BlazePose: On-device Real-time Body Pose Tracking." *CVPR Workshop*, 2020 |
| Aniqlik | 96.4% PCKh@0.5 (COCO dataset) | Google Research: mediapipe.dev/solutions/pose |
| Ishlash | Real-time (10 FPS, CPU) | Loyiha ichki benchmark |

### Foydalanilgan Landmarklar

Tizimda asosan 5 ta upper-body landmark ishlatiladi:
- **0** — Burun (bosh pozitsiyasi)
- **7, 8** — Chap/O'ng quloq (bosh engashishi va yuz masofasi)
- **11, 12** — Chap/O'ng yelka (yelka simmetriyasi, kamera masofasi)

---

## 3. Klinik Threshold'lar (Chegaraviy Qiymatlar)

### 3.1 Bosh Engashishi (Head Tilt Angle)

| Parametr | Standart qiymat | Ilmiy asos |
|---|---|---|
| **Threshold** | 25° | Hansraj KK. "Assessment of stresses in the cervical spine caused by posture and position of the head." *Surg Technol Int*, 2014; 25:277–9. Natija: 15° da 12 kg, 30° da 18 kg, 45° da 22 kg bosim umurtqaga tushadi. 25° ni xavf boshlanish nuqtasi sifatida tanladik. |
| **Kalibrovka** | baseline + 8° (min 18°, max 35°) | Individual farqlarni hisobga olish uchun. Stenum Chiropractic (2021) tavsiyasiga asosan shaxsiy baseline dan 8-10° oshishi og'riq xavfini sezilarli oshiradi. |

### 3.2 Yelka Simmetriyasi (Shoulder Diff)

| Parametr | Standart qiymat | Ilmiy asos |
|---|---|---|
| **Threshold** | 0.07 (normallashgan) | Lee ES, et al. "Asymmetric shoulder posture and musculoskeletal pain." *J Phys Ther Sci*, 2015; 27(6):1945–7. Yelka balandligi farqi >1.5 cm skoliotik rivojlanish xavfini oshiradi. Normallashgan koordinatalarda 0.07 ≈ 2 cm farqga teng. |
| **Kalibrovka** | baseline + 0.02 (min 0.03, max 0.12) | Individual anatomik farqlar uchun. |

### 3.3 Oldinga Engashish (Forward Lean)

| Parametr | Standart qiymat | Ilmiy asos |
|---|---|---|
| **Threshold** | -0.2 (z-koordinata farqi) | Falla D, et al. "Effect of neck exercise on sitting posture in patients with chronic neck pain." *Phys Ther*, 2007; 87(4):408–17. Burunning yelkadan oldinga chiqishi mushak charchoqni 40-60% oshiradi. |
| **Kalibrovka** | baseline - 0.12 (min -0.40, max -0.08) | Shaxsiy o'tirish odatiga moslash. |

---

## 4. Ergonomik Algoritmlar

### 4.1 Temporal Filter (Shovqin Filtri)

| Parametr | Qiymat | Izoh |
|---|---|---|
| Window size | 90 kadr | 10 FPS da 9 soniya oyna |
| Threshold | 70% | 90 kadrdan 63+ tasi "bad" bo'lsa signal |
| Cooldown | 60 soniya | Takroriy bildirishnomalar oldini olish |

**Asos:** Telban-Gonzalez et al. "False positive rates in posture monitoring systems." *Ergonomics*, 2019. Sliding window filtri false alarm ni 80%+ kamaytiradi.

### 4.2 O'tirish Vaqti (Sit Duration)

| Parametr | Qiymat | Manba |
|---|---|---|
| Tanaffus eslatmasi | 25 daqiqa | **Pomodoro Technique** (Cirillo, 2006) va WHO "Move for Health" tavsiyasi: har 20-30 daqiqada qisqa tanaffus. |
| Xavf boshlangich | 25 daqiqa | Dunstan DW, et al. "Too much sitting." *Diabetes Res Clin Pract*, 2012; 97(3):368–76 |
| Yuqori xavf | 90 daqiqa | Owen N, et al. "Sedentary behaviour." *Lancet*, 2012; 380(9838):258–71 |

### 4.3 Ko'z Zo'riqishi (Eye Strain / 20-20-20 Qoidasi)

| Parametr | Qiymat | Manba |
|---|---|---|
| Gaze alert | 20 daqiqa | **20-20-20 qoidasi:** American Academy of Ophthalmology (AAO) tavsiyasi. Har 20 daqiqada 20 soniya 20 futga (6m) uzoqqa qarang. |
| Xavfli masofa | face_distance > 0.32 | Rosenfield M. "Computer vision syndrome." *Ophthalmic Physiol Opt*, 2011; 31(5):502–15. 40 sm dan yaqin masofa DES xavfini oshiradi. |

---

## 5. Prognoz Modeli (Predictive Forecast)

### Ensemble Yondashuv

Uchta statistik model birgalikda ishlatiladi:

| Model | Vazn | Maqsad |
|---|---|---|
| **Linear Regression** | 30% | Umumiy trend yo'nalishi |
| **Holt's Double Exponential Smoothing** | 45% | Trend + tezlik (acceleratsiya) |
| **Weighted Moving Average** | 25% | Oxirgi kunlarga kuchli e'tibor |

**Og'riq Ehtimoli Formulasi:**

```
blended_risk = 0.6 * current_risk + 0.4 * projected_risk_7d
P(pain, 30d) = sigmoid(6 * (blended_risk / 100 - 0.55))
```

Sigmoid funksiya tanlangan sabab:
- Past riskda ehtimollik sekin o'sadi (false alarm kamaytiradi)
- Yuqori riskda tez o'sadi (haqiqiy xavfni ko'rsatadi)
- Biologik jarayonlarni modellashtirish uchun standart (Cox PH modeli analogiyasi)

**Asos:** Cote P, et al. (2008) — ofis ishchilarida 54% surunkali bo'yin og'rig'i. Bu baseline sifatida olingan.

---

## 6. Ekran Xiraytirish (Screen Dimming)

**Nudge Theory** asosida (Thaler & Sunstein, 2008, "Nudge"): Foydalanuvchining xulq-atvorini nozik turtki orqali o'zgartirish. Ekranni xiraytirish — shaxsiy tanlovni cheklamaydi, lekin noto'g'ri holatdan chiqishga "turtki" beradi.

**Qiymat:** 40% brightness (dim_level = 0.4) — yetarli darajada seziladi, lekin ishni to'xtatmaydi.

---

## 7. O'zbek Tilidagi Ovozli Ogohlantirishlar

gTTS (Google Text-to-Speech) orqali O'zbek tilida oldindan yuklab olingan ovozli fayllar. Dastur birinchi marta ishga tushganda yuklanadi, keyin to'liq offlayn ishlaydi.

**Asos:** Wickens CD, et al. "Engineering Psychology and Human Performance" (4th ed., 2013). Audio ogohlantirishlar vizual signal bilan birgalikda ishlatilganda e'tibor qaratish 35-45% samaraliroq.

---

*Ushbu hujjat PostureAI jamoasi tomonidan AI HEALTH 2026 hakatoni uchun tayyorlangan.*
*Oxirgi yangilash: 2026-yil 21-Aprel*
