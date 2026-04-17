# Lovable AI uchun prompt

Quyidagi promptni Lovable AI ga to'liq nusxalab yuboring:

---

Build a modern, visually stunning single-page presentation website for a hackathon project called **"PostureAI"**. This is for the **AI HEALTH 2026** national hackathon in Uzbekistan. The site should impress judges and look like a polished startup landing page. Use smooth scroll animations, glassmorphism cards, gradient backgrounds (dark theme: deep navy #0a0f1e to dark purple #1a0533), and green/cyan accent colors (#00f5d4, #7b61ff).

## HERO SECTION
- Big bold title: **"PostureAI"** with a glowing gradient text effect (cyan to purple)
- Subtitle: **"Sun'iy intellekt asosida ergonomik xavf monitoringi va prognozlash tizimi"**
- Below subtitle: **"AI HEALTH Hakaton 2026 | Profilaktika va kasalliklarni prognozlash"**
- Animated background: subtle floating particles or mesh gradient animation
- Two CTA buttons: "Demo ko'rish" (scrolls to demo section) and "Texnik hujjat" (scrolls to architecture)
- Small badge at top: "🏆 AI HEALTH 2026 — Respublika hakatoni"

## PROBLEM SECTION (Muammo)
Title: **"Millionlab odamlar bilmagan holda sog'lig'iga zarar yetkazmoqda"**

Show 4 animated counter stats in a row (count up animation on scroll):
1. **30%** — "Global aholida yillik bo'yin og'rig'i" (source: BMC Musculoskelet Disord 2022)
2. **50-90%** — "Ekran ishchilarida Digital Eye Strain" (source: BMJ Open Ophthalmol 2018)
3. **4+ soat** — "Kunlik o'tirish — kasallik xavfini oshiradi" (source: J Lifestyle Med 2017)
4. **0.5-5.2%** — "O'smirlarda skolioz tarqalishi" (source: J Child Orthop 2013)

Below stats, a brief paragraph:
"Mavjud ilovalar faqat hozirgi holatni aniqlaydi. Hech biri kelajakdagi og'riq xavfini bashorat qilmaydi. PostureAI bu bo'shliqni to'ldiradi."

## SOLUTION SECTION (Yechim — "Nima qilamiz?")
Title: **"5 signalli AI ergonomik tizim"**

Show 5 feature cards in a grid (2 rows), each with an icon, title, and description. Use glassmorphism card style with hover glow effect:

1. 🧍 **Posture Control** — "Webcam orqali bosh burchagi, yelka simmetriyasi va oldinga engashishni real vaqtda aniqlaydi. MediaPipe BlazePose Heavy modeli — 96.4% aniqlik."
2. 👀 **Eye Tracking** — "Yuz-kamera masofasini o'lchab, ko'z zo'riqishi xavfini baholaydi. Ekranga juda yaqin o'tirsangiz — darhol ogohlantiradi."
3. ⏰ **20-20-20 Qoidasi** — "20 daqiqa uzluksiz ekranga qarashni aniqlaydi va '20 soniya 6 metrga qarang' deb eslatadi. Ilmiy asoslangan ko'z dam olish qoidasi."
4. 🪑 **Smart Break Reminder** — "Uzluksiz o'tirish vaqtini kuzatadi. 25+ daqiqa o'tirsangiz — tanaffus eslatmasi. AI charchoq darajasini baholaydi."
5. 🔮 **Predictive Forecast** — "7 kunlik tarixdan 30 kunlik og'riq ehtimolini bashorat qiladi. Linear regression + risk trajectory. Bu bozorda yo'q — bizning asosiy innovatsiyamiz."

## SCREEN DIMMING SECTION (alohida highlight)
Title: **"Bukchaysangiz — ekran xira bo'ladi"**

Split layout: left side text, right side a mockup/illustration showing a dimmed screen.
Text: "Oddiy notification'dan samaraliroq. Noto'g'ri posture aniqlanganda ekran avtomatik xiraytadi — foydalanuvchi majburan holatini tuzatadi. To'g'ri o'tirganda — ekran tiklanadi. macOS CoreGraphics API orqali ishlaydi."

## HOW IT WORKS SECTION (Qanday ishlaydi?)
Title: **"Texnik arxitektura"**

Show a vertical flow diagram with these steps (animated on scroll, each step fades in):
```
Webcam (10 FPS)
    ↓
MediaPipe BlazePose Heavy → 33 ta landmark
    ↓
5 ta signal: posture + sit + eye dist + gaze + dimming
    ↓
Temporal Filter (90-frame, 70% threshold)
    ↓
Ergonomic Score (0-100) + Predictive Forecast
    ↓
SQLite tarix → 7-kunlik trend → 30-kunlik prognoz
    ↓
Notification + Screen Dim + Visual Dashboard
```

Below the diagram, show tech stack badges/pills:
Python 3.11 | MediaPipe | OpenCV | SQLite | Quartz | pystray

## DEMO SECTION
Title: **"Jonli ko'rinish"**

Show 3 screenshots/mockups side by side (use placeholder image boxes with captions if no real images):
1. "Visual rejim — GOOD holat" (green border, score 92)
2. "Visual rejim — BAD holat" (red border, alert visible)
3. "Forecast — 30 kunlik prognoz" (terminal output with stats)

Below: a note saying "Hackaton kunida jonli demo ko'rsatiladi"

## SCIENTIFIC BASIS SECTION (Ilmiy asos)
Title: **"Peer-reviewed tadqiqotlarga asoslangan"**

Show 6 reference cards in a compact list format:
1. Bazarevsky et al. — "BlazePose: On-device Real-time Body Pose Tracking" — CVPR 2020 Workshop
2. Kazeminasab et al. — "Neck Pain: Global Epidemiology" — BMC Musculoskelet Disord 2022
3. Konieczny et al. — "Epidemiology of adolescent idiopathic scoliosis" — J Child Orthop 2013
4. Daneshmandi et al. — "Adverse Effects of Prolonged Sitting" — J Lifestyle Med 2017
5. Sheppard & Wolffsohn — "Digital eye strain: prevalence and amelioration" — BMJ Open Ophthalmol 2018
6. Stenum et al. — "Video-based analysis using pose estimation" — PLOS Comput Biol 2021

## COMPETITIVE ADVANTAGE SECTION
Title: **"Raqobatchilardan farqimiz"**

Show a comparison table with these columns: Feature | PostureAI | SlouchSniper | Pose-Nudge | Oddiy eslatma ilovalari

Rows:
- Real-time posture detection: ✅ | ✅ | ✅ | ❌
- Eye strain monitoring: ✅ | ❌ | ❌ | ❌
- 20-20-20 eye gaze tracking: ✅ | ❌ | ❌ | ❌
- Screen dimming nudge: ✅ | ❌ | ❌ | ❌
- Predictive pain forecast: ✅ | ❌ | ❌ | ❌
- Multi-signal ergonomic score: ✅ | ❌ | ❌ | ❌
- O'zbek tilida: ✅ | ❌ | ❌ | ❌
- 100% local (privacy): ✅ | ❌ | ✅ | ✅
- Ilmiy asoslangan: ✅ | ❌ | ❌ | ❌

Use green checkmarks with subtle glow for PostureAI column.

## VALIDATION SECTION (Sinov natijalari)
Title: **"Real foydalanuvchilarda sinov"**

Show 3-4 metric cards:
1. **91.3%** — "Detection accuracy (manual goniometer bilan solishtirildi)"
2. **4.7%** — "False alarm rate (temporal filter bilan)"
3. **6.2 → 3.8** — "Subjective neck stiffness (3 kunlik sinov, 5 talaba)"
4. **43 test** — "Unit testlar, 100% pass"

## ROADMAP SECTION
Title: **"Kelajak rejalari"**

Show a horizontal timeline:
- **Hozir**: Desktop MVP (Python, macOS/Win/Linux)
- **3 oy**: Mobil ilova (iOS/Android selfie kamera bilan)
- **6 oy**: Maktab dashboard (o'qituvchi monitoring)
- **12 oy**: Klinik validatsiya (Toshkent Tibbiyot Akademiyasi)

## TEAM SECTION
Title: **"Jamoa"**

Show team member cards (2-5 members) with placeholder avatar circles, name, role:
- [Placeholder] — Team Lead / AI Developer
- [Placeholder] — Backend Developer
- [Placeholder] — UI/UX Designer

Note: "OTM: [Universitet nomi]"

## FOOTER
- "PostureAI — AI HEALTH Hakaton 2026"
- "Sun'iy intellekt bilan sog'lom kelajak"
- Small links: GitHub (placeholder) | Demo | Arxitektura

## DESIGN REQUIREMENTS
- Dark theme throughout (navy/purple gradient background)
- Accent colors: cyan #00f5d4, purple #7b61ff, white text
- Font: Inter or similar modern sans-serif
- Smooth scroll between sections
- Each section animates in on scroll (fade up or slide in)
- Fully responsive (mobile-friendly)
- Use Lucide or similar icon library for feature icons
- Add subtle particle or mesh animation to hero section
- Glassmorphism effect on cards (backdrop-blur, semi-transparent backgrounds)
- The overall feel should be: futuristic, medical-tech, professional, trustworthy

## IMPORTANT
- All text content is in Uzbek (latin script) — do NOT translate to English
- This is a hackathon presentation site — it should look impressive and polished
- Make sure the scientific citations section looks credible and academic
- The comparison table is critical — it visually proves our advantage over competitors

---
