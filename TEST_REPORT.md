# Ijtimoiy-Tibbiy Sinov Dalolatnomasi
## PostureAI MVP (Minimal Ishchan Mahsulot) Sinovi Natijalari

**Hakaton:** AI HEALTH - 2026 Respublika Hakatoni  
**Yo'nalish:** Profilaktika va kasalliklarni prognozlash tizimlari  
**Loyiha nomi:** PostureAI  
**Sinov o'tkazilgan sana:** 2026-yil 12-14-Aprel (3 kun)  
**Sinov muvofiqlashtiruvchisi:** PostureAI jamoasi lideri

---

### 1. Sinov Maqsadi va Dolzarbligi
Ushbu sinovdan maqsad — **PostureAI** desktop ilovasining ijtimoiy-tibbiy samaradorligini amalda isbotlash, dasturiy ta'minotning noto'g'ri o'tirish odatlarini o'zgartira olishi va kunlik bo'yin va yelka mushaklaridagi zo'riqishni (stiffness) kamaytira olishini validatsiya qilish (Hakaton qoidalari 5.2.3-band, 3-mezoniga muvofiq).

**Sinov gipotezasi:** PostureAI tizimini 3 kun uzluksiz qo'llash to'g'ri o'tirish foizini kamida 20% ga oshiradi va subyektiv bo'yin og'rig'ini kamida 2 ballga kamaytiradi.

### 2. Ishtirokchilar va Shartlar
Sinov jalb qilingan ko'ngilli 5 nafar talaba/magistrantlarda (kuniga o'rtacha 5-7 soat kompyuter qarshisida o'tiruvchi, hech qanday klinik surunkali kasalligi yo'q shaxslarda) o'tkazildi.  
  
**Sinov parametrlari:**
- Tizim davomiyligi: 3 ish kuni (72 soat)
- Asosiy qurilma: Talabalarning shaxsiy noutbuklari (Windows/macOS), o'rnatilgan web-kameralari orqali (720p/1080p)
- Qo'shimcha uskunalar: Yo'q (Dastur avtomatik orqa fonda ishladi)
- Bildirishnoma turi: Vizual (tray icon, ekran xiraytirish) + Audio (O'zbek tilidagi ovozli ogohlantirish)

> *Ishtirokchilar maxfiyligini ta'minlash maqsadida ismlar shifrlangan:*

| # | Ishtirokchi | Yosh | Kasb/Ta'lim | Kunlik kompyuter vaqti | OS |
|:---:|:---|:---:|:---|:---:|:---:|
| 1 | Ishtirokchi A | 21 | TATU, Dasturiy injiniring | 8 soat | Windows 11 |
| 2 | Ishtirokchi B | 23 | TMA, Magistrant | 6 soat | macOS 14 |
| 3 | Ishtirokchi C | 20 | TDTU, Talaba | 5 soat | Windows 10 |
| 4 | Ishtirokchi D | 22 | Masofaviy ishlovchi (Frilanser) | 9 soat | Windows 11 |
| 5 | Ishtirokchi E | 19 | Maktab/Lisey o'quvchisi | 4 soat | macOS 13 |

### 3. Asosiy Ko'rsatkichlar (KPI)
1. **Dasturning aniqlik darajasi (Detection Accuracy):** Haqiqiy qaddi-qomatga nisbatan noto'g'ri odatni ajrata olishi (MediaPipe kameradan)
2. **Posturaviy tuzalish foizi:** Talabaning noto'g'ri holatdan qancha vaqt ichida to'g'ri holatga qaytishi
3. **Subyektiv og'riq ko'rsatkichi (Subjective Neck Stiffness Scale, SNS):** 0 dan 10 gacha bo'lgan og'riq va qotish reytingi (0 = og'riq yo'q, 10 = o'ta kuchli charchoq/og'riq). Testdan oldin va 3 kunlik testdan so'ng o'lchandi
4. **False Alarm Rate:** Noto'g'ri bildirishnomalar foizi
5. **Ergonomic Score o'rtachasi:** Tizimning ichki sifat ko'rsatkichi (0-100)

### 4. Sinov Jarayoni va Texnik Ma'lumotlar

**4.1. Tizimning ishlash jarayoni (MVP ishchanligi):**  
Dastur belgilangan tartibda orqa fonda ishladi va quyidagi xatoliklarni aniq fiksatsiya qildi:
- Boshi 25° dan ortiq oldinga tushganda (Head tilt) — Hansraj (2014) asosida
- Ekran tomonga 20 sm dan yaqin kelganda (Eye strain) — Rosenfield (2011) asosida
- Tanaffussiz o'tirish vaqti 25 daqiqadan oshganda (Sedentary time) — WHO tavsiyasi asosida
- Yelkalar 0.07 dan ortiq nosimmetrik bo'lganda — Lee et al. (2015) asosida

**4.2. Temporal Filter ishlash samaradorligi:**  
"Sliding window" algoritmi (90 kadr, 70% threshold) orqali mayda-chuyda tasodifiy engashishlar (masalan: sichqonchaga qarash, telefonni olish) e'tiborga olinmay faqat zararli uzoq vaqt noto'g'ri o'tirishga bildirishnoma berish isbotlandi.

**4.3. Tizim resurslari:**  
O'rtacha CPU yuklamasi: 8-12% (MacBook Air M1), 15-20% (Intel i5 10th gen). RAM: ~180 MB.

### 5. Individual Natijalar (Har Bir Ishtirokchi Bo'yicha)

#### 5.1. To'g'ri O'tirish Foizi (Good Posture %)

| Ishtirokchi | 1-kun (bazaviy) | 2-kun | 3-kun (yakuniy) | O'zgarish |
|:---:|:---:|:---:|:---:|:---:|
| A | 42% | 58% | 71% | **+29%** |
| B | 51% | 64% | 78% | **+27%** |
| C | 38% | 52% | 68% | **+30%** |
| D | 47% | 60% | 72% | **+25%** |
| E | 48% | 61% | 76% | **+28%** |
| **O'rtacha** | **45.2%** | **59.0%** | **73.0%** | **+27.8%** |

#### 5.2. Subyektiv Bo'yin Qotishi (SNS, 0-10 ball)

| Ishtirokchi | Testdan oldin | Testdan keyin | O'zgarish |
|:---:|:---:|:---:|:---:|
| A | 7.0 | 4.2 | **-2.8** |
| B | 5.5 | 3.1 | **-2.4** |
| C | 6.8 | 4.0 | **-2.8** |
| D | 6.0 | 3.8 | **-2.2** |
| E | 5.7 | 3.9 | **-1.8** |
| **O'rtacha** | **6.2** | **3.8** | **-2.4** |

#### 5.3. Uzluksiz O'tirish Davomiyligi (Maksimal)

| Ishtirokchi | Testdan oldin | Testdan keyin | O'zgarish |
|:---:|:---:|:---:|:---:|
| A | 135 daqiqa | 42 daqiqa | **-93 daqiqa** |
| B | 90 daqiqa | 38 daqiqa | **-52 daqiqa** |
| C | 150 daqiqa | 45 daqiqa | **-105 daqiqa** |
| D | 120 daqiqa | 40 daqiqa | **-80 daqiqa** |
| E | 105 daqiqa | 44 daqiqa | **-61 daqiqa** |
| **O'rtacha** | **120 daq** | **41.8 daq** | **-78.2 daq** |

### 6. Yig'ma Natijalar va Statistik Tahlil

#### 6.1. Asosiy KPI'lar

| Ko'rsatkich | Testdan Oldin | Testdan Keyin | O'zgarish | p-qiymat* |
|:---|:---:|:---:|:---:|:---:|
| **To'g'ri o'tirish (Good Posture) foizi** | 45.2% | 73.0% | **+27.8%** | p < 0.01 |
| **Bosh/Bo'yin subyektiv qotishi (SNS)** | 6.2 ball | 3.8 ball | **-2.4 ball** | p < 0.01 |
| **Uzluksiz o'tirishning max davomiyligi** | 120 daq | 41.8 daq | **-78.2 daq** | p < 0.01 |
| **False Alarm Rate** | — | 4.7% | — | — |
| **Tizim detection accuracy** | — | 94.3% | — | — |

*\*p-qiymat: paired t-test (n=5). p < 0.05 statistik jihatdan muhim (significant) hisoblanadi.*

#### 6.2. Ergonomic Score O'rtachasi (Tizim Ichki Ko'rsatkichi)

| Kun | O'rtacha Ergonomic Score | O'rtacha Posture Score |
|:---:|:---:|:---:|
| 1-kun (bazaviy) | 52.4 | 48.6 |
| 2-kun | 64.8 | 61.2 |
| 3-kun (yakuniy) | 74.2 | 71.8 |

#### 6.3. Predictive Forecast Modeli Validatsiyasi
Ishtirokchilar bazasida 3 kun ichida yig'ilgan statistika (SQLite) ensemble modeli (Linear + Holt + WMA) yordamida keyingi 30 kunga ehtimolliklarni hisoblab berdi.

| Ishtirokchi | 30 kunlik og'riq ehtimoli (1-kun) | 30 kunlik og'riq ehtimoli (3-kun) | Trend |
|:---:|:---:|:---:|:---:|
| A | 62% | 34% | Pasaymoqda |
| B | 48% | 22% | Pasaymoqda |
| C | 67% | 38% | Pasaymoqda |
| D | 55% | 30% | Pasaymoqda |
| E | 52% | 28% | Pasaymoqda |

*Barcha ishtirokchilarda tizim to'g'ri yo'nalishni aniqladi: posture yaxshilanganda og'riq ehtimoli pasaydi.*

### 7. False Alarm Tahlili

| Turi | Soni (3 kun jami) | Foiz |
|:---|:---:|:---:|
| **Haqiqiy ogohlantirish (True Positive)** | 287 | 95.3% |
| **Noto'g'ri ogohlantirish (False Positive)** | 14 | 4.7% |
| **Jami** | 301 | 100% |

False alarm sabablari:
- Telefonni olish paytida qisqa engashish (8 marta)
- Stol ustiga biror narsani olish (4 marta)
- Kamera ko'rinishi tashqarisidagi harakat (2 marta)

### 8. Ishtirokchilar Fikrlari (Subyektiv Baholash)

| Ishtirokchi | Fikr |
|:---|:---|
| A | "Birinchi kuni bezovta qildi, lekin 2-kunga o'rganib qoldim. Hozir o'zim bilaman qachon noto'g'ri o'tirganligimnini" |
| B | "O'zbek tilidagi ovozli ogohlantirish juda yaxshi — tushunishga oson" |
| C | "Dastur juda yengil ishlaydi, kompyuter sekinlashmadi. Kamerani yopib qo'ysam ham ishlamaydi — bu yaxshi" |
| D | "9 soat ishlashda eng foydali narsasi — tanaffus eslatmasi. Oldin 2-3 soat uzluksiz o'tirardim" |
| E | "Boshqa ilovalardan farqi — bu shunchaki 'tik o'tir' demaydi, balki qaysi mushak qanday qilib yomonlashayotganini ko'rsatadi" |

### 9. Sinov Xulosasi

> **PostureAI tizimi o'zining dastlabki testlaridan (MVP validatsiyasidan) to'liq, muvaffaqiyatli ravishda o'tdi.**
>
> Asosiy topilmalar:
> 1. To'g'ri o'tirish odati **+27.8%** ga yaxshilandi (statistik significant, p < 0.01)
> 2. Subyektiv bo'yin og'rig'i **-2.4 ballga** pasaydi (10 balldan)
> 3. Uzluksiz o'tirish **-78 daqiqaga** qisqardi (120 → 42 daqiqa)
> 4. False alarm rate **4.7%** — klinik standartlarga mos (< 10% talab qilinadi)
> 5. Predictive Forecast modeli barcha ishtirokchilarda **to'g'ri trend** ko'rsatdi
>
> **Sinov gipotezasi tasdiqlandi:** PostureAI 3 kunda to'g'ri o'tirish foizini 20%+ ga oshirdi va og'riqni 2+ ballga kamaytirdi.

***
*Tasdiqladi: PostureAI jamoasi lideri / Test muvofiqlashtiruvchisi*  
*Imzo o'rni:* _________________  
*Sana:* 2026 yil 15 Aprel
