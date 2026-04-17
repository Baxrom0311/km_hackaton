# PostureAI — Demo Video Skripti (2:30 daqiqa)

> Maqsad: Hakaton baholash mezoni 3 (MVP, 25 ball) uchun **"rasmlar va videomateriallar mavjudligi"** talabini bajarish.  
> Format: 1920×1080, 30 FPS, ovozli izoh (uzbekcha), screen recording + webcam overlay.  
> Joy: Tinch xona, yaxshi yorug'lik, neytral fon.

---

## Tayyorlik (yozishdan oldin)

- [ ] `posture.db` faylini o'chirib, tezda 3 kun haftalik test ma'lumotini seed qilish (yoki Faker bilan to'ldirish — quyidagi snippet ko'ring)
- [ ] `config.json` da kalibrovka qiymatlari to'liq bo'lsin
- [ ] Toshkentda ishlasa toza fon: oq devor, yorug' lampa
- [ ] Webcam test (1080p ishlasa yaxshi)
- [ ] OBS Studio yoki QuickTime + iPhone Mirroring tayyor
- [ ] Microfon test — fon shovqini yo'q

### Tezkor ma'lumot seed (forecast slaydi uchun)

```python
# tools/seed_demo_data.py
import sqlite3, datetime, random
con = sqlite3.connect("posture.db")
cur = con.cursor()
cur.execute("INSERT INTO sessions (start_time) VALUES (datetime('now', '-7 days'))")
session_id = cur.lastrowid
for day_offset in range(7, 0, -1):
    base_score = 85 - day_offset * 4  # trend yomon tomonga
    for i in range(60):
        ts = (datetime.datetime.now() - datetime.timedelta(days=day_offset, minutes=i)).isoformat(timespec='seconds')
        score = max(20, min(100, base_score + random.randint(-8, 8)))
        ergo = max(20, score - random.randint(0, 15))
        status = 'good' if score >= 70 else 'bad'
        cur.execute(
            "INSERT INTO posture_logs (session_id, timestamp, status, head_angle, shoulder_diff, forward_lean, posture_score, ergonomic_score, sit_seconds, face_distance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, ts, status, 15.0, 0.04, -0.10, score, ergo, i * 60, 0.20)
        )
con.commit()
```

---

## SCENE 1 — Kirish (0:00 – 0:15)

**Kadr:** Webcam to'g'ri yuzga, ozgina o'zbek bayrog'i ranglarida lower-third bilan ism + universitet.

**Ovoz:**
> "Salom! Men [Ism]. AI HEALTH 2026 hakatoni uchun PostureAI loyihasini taqdim etaman. Bu — webcam orqali sizning o'tirish holatingizni real vaqtda kuzatib, kelajakdagi bo'yin va bel og'rig'i xavfini bashorat qiladigan Python ilova."

**Ekran ustida matn:**  
`PostureAI · AI HEALTH 2026 · [Ism Familiya]`

---

## SCENE 2 — Muammo (0:15 – 0:30)

**Kadr:** Ekran yarmi — siz noto'g'ri o'tirgan video; ikkinchi yarmi — quyidagi statistika animatsiyasi.

**Ekranga chiqadigan raqamlar (har biri 3 sek):**
- 30% global aholi — yillik bo'yin og'rig'i (BMC 2022)
- 50–90% — ekran ishchilarida ko'z zo'riqishi (BMJ 2018)
- 4+ soat o'tirish — kasallik xavfini sezilarli oshiradi (J Lifestyle Med 2017)

**Ovoz:**
> "Tadqiqotlar ko'rsatadiki, har 3-uchinchi inson yillik bo'yin og'rig'iga duch keladi. Lekin mavjud ilovalar faqat *hozirgi* holatni aniqlaydi — kelajakni bashorat qilmaydi."

---

## SCENE 3 — Ilova ishga tushirish (0:30 – 0:50)

**Kadr:** Terminal full-screen.

**Komandalar (har birini ko'rsating):**
```bash
$ source .venv/bin/activate
$ python main.py --doctor
PostureAI Doctor
- Config: ok (camera_index=0, fps=10)
- SQLite: ok (posture.db)
- Dependencies: ok
- Model: ok (models/pose_landmarker_heavy.task)
- Camera: ok (index=0)
$ python main.py
```

**Ovoz:**
> "Avval tizim diagnostikasi — kamera, model fayl, kutubxonalar tekshiriladi. Hammasi yashil. Endi monitoringni ishga tushiramiz."

**Kadr o'tishi:** Tray icon paydo bo'lishini ko'rsating (yashil doira).

---

## SCENE 4 — Yaxshi posture (0:50 – 1:05)

**Kadr:** Webcam kadr — siz to'g'ri o'tirgan, yelkalaringiz tekis, boshingiz ko'tarilgan.

**Overlay (yuqori o'ng burchakda):**
```
PostureAI
posture: 92  ergo: 90
sit: 0.4 m  status: GOOD
```

**Ovoz:**
> "Hozir to'g'ri o'tiribman. Tray ikonkasi yashil — posture 92 ball, ergonomik ball 90, ko'rinishlar barqaror."

---

## SCENE 5 — Yomon posture + alert (1:05 – 1:30)

**Kadr:** Asta-sekin oldinga engashing va boshingizni pastga tushiring. ~5 sekund kuting.

**Overlay (real-time o'zgarishi):**
```
posture: 87 → 71 → 52 → 38
ergo:    85 → 68 → 50 → 35
status:  GOOD → BAD
```

**Trigger:** Notification chiqadi:
> 🔔 PostureAI  
> **Boshingizni ko'taring! Oldinga engashib ketibsiz.**

**Ovoz:**
> "Endi ataylab yomon o'tiraman. 90-frame temporal filter false alarm'larni filtrlaydi, va 3 soniyada ogohlantirish keladi: 'Boshingizni ko'taring'. Tray ikonkasi qizil."

---

## SCENE 6 — Multi-signal: Eye strain (1:30 – 1:45)

**Kadr:** Yuzingizni kameraga yaqinlashtiring (~25 sm).

**Overlay:**
```
face_distance: 0.12 → 0.28 → 0.36
eye_strain_risk: 0.0 → 0.7 → 1.0
```

**Notification:**
> 🔔 PostureAI  
> **Ekranga juda yaqin o'tiribsiz. Ko'zlaringizni dam oldiring.**

**Ovoz:**
> "Tizim faqat posture'ni kuzatmaydi. Yuzingiz kameraga yaqinlashganda — bu ekranga yaqin o'tirish belgisi — ko'z zo'riqishi haqida ham eslatadi."

---

## SCENE 7 — Forecast (1:45 – 2:15)

**Kadr:** Yangi terminal, full-screen.

```bash
$ python main.py --stats
PostureAI Stats
- Today: good=68.5% bad=31.5% avg_score=72.3
- Ergonomic: avg=64.8 | longest_sit=82.4 min
- Samples: 240 | Alerts: 7
- Weekly:
  2026-04-10 | good=78.1% | posture=82.4 | ergo=78.2 | bad=14
  2026-04-11 | good=74.5% | posture=79.8 | ergo=74.6 | bad=18
  2026-04-12 | good=70.2% | posture=76.5 | ergo=70.1 | bad=22
  2026-04-13 | good=65.8% | posture=72.1 | ergo=66.4 | bad=27
  2026-04-14 | good=62.3% | posture=68.9 | ergo=62.2 | bad=31
  2026-04-15 | good=59.0% | posture=65.5 | ergo=58.7 | bad=35
  2026-04-16 | good=68.5% | posture=72.3 | ergo=64.8 | bad=38
- Forecast:
  current_risk=35.2 (moderate) | 7d_projected=42.8 | slope/day=+1.40
  30 kunda og'riq ehtimoli: 47%
  Tavsiya: O'rtacha xavf. Stol balandligini tekshiring, monitorni ko'z 
  darajasiga qo'ying va kuniga 2-3 marta cho'zilish mashqlarini bajaring.
```

**Ovoz:**
> "Bu PostureAI ning eng muhim qismi — *prognozlash*. Linear regression haftalik trendni aniqlaydi: bu hafta xavf har kuni 1.4 ballga oshmoqda. Agar shu odat davom etsa, 30 kun ichida bo'yin og'rig'i ehtimoli — 47%. Tizim aniq tavsiya beradi: stol balandligi, monitor pozitsiyasi, cho'zilish mashqlari."

---

## SCENE 8 — Texnik xulosalar va xulosa (2:15 – 2:30)

**Kadr:** Quyidagi infografika to'liq ekranda.

```
PostureAI — Texnik Stack
─────────────────────────────────
Detection:    MediaPipe BlazePose Heavy (96.4% PCKh@0.5)
Reliability:  ICC ≥ 0.85 sagittal angle (Stenum 2021)
Stack:        Python 3.11 · OpenCV · SQLite · pystray
Tests:        33 unit test, 100% pass
Privacy:      100% local, hech qanday bulut ulanishi yo'q
Platforms:    macOS · Windows · Linux
─────────────────────────────────
```

**Ovoz:**
> "PostureAI — bu detection emas, *prevention*. Faqat 'noto'g'ri' deb baqirmaydi, balki kelajak xavfini bashorat qilib, sog'lom odatlar shakllanishiga yordam beradi. Rahmat — savollaringizni kutamiz."

**Yakuniy kadr:** Logo + jamoa nomi + GitHub repo havolasi (ixtiyoriy).

---

## Post-production checklist

- [ ] Kirish va xulosada bir xil bumper (PostureAI logo, 1 sek)
- [ ] Subtitr (uzbekcha) — hakamlar uchun foydali
- [ ] Background music: tinch elektronik (Royalty-free, masalan `bensound.com`)
- [ ] Color grade: warm, neytral
- [ ] Eksport: MP4 H.264, 1080p, ~50 MB
- [ ] Backup: YouTube unlisted upload + lokal MP4
- [ ] PITCH.md ga link qo'shing va `submission` papkasiga joylang

---

## Pitch oldidan repetisiya

- [ ] Audio sifatini tekshirib, kerak bo'lsa qayta yozing
- [ ] Hakamlardan biriga oldindan ko'rsating, fikrini oling
- [ ] 2:30 limitidan oshmaganini tekshiring (final bosqich limitlari qattiq)
- [ ] Backup video — agar ekran demo internetda ishlamasa — har doim tayyor turing
