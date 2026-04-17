# PostureAI Desktop MVP

`PostureAI` webcam orqali foydalanuvchining o'tirish holatini tahlil qiladi, noto'g'ri posture uzoq davom etsa ogohlantiradi va statistikani SQLite bazaga yozadi.

## Hozirgi holat

- `detector.py`: posture metrikalari va MediaPipe/OpenCV detection loop
- `filter.py`: sliding-window temporal filter
- `notifier.py`: cross-platform notification wrapper
- `storage.py`: session, logs va alerts uchun SQLite qatlam
- `tray.py`: system tray mavjud bo'lsa tray host, bo'lmasa console fallback
- `main.py`: to'liq ishga tushirish oqimi

## Ishga tushirish

MediaPipe amalda eng barqaror `Python 3.11` da ishlaydi. Joriy tizimda boshqa versiya bo'lsa, 3.11 virtual environment tavsiya etiladi.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Repo ichida model fayli ham ishlatiladi:

`models/pose_landmarker_heavy.task`

Shaxsiy threshold larni kalibrovka qilish:

```bash
python main.py --calibrate
```

Kalibrovka vaqtida 10-12 soniya kameraga to'g'ri posture bilan o'tirib turing. Natija `config.json` ga yoziladi.

Tray muammoli bo'lsa yoki terminaldan ishlatmoqchi bo'lsangiz:

```bash
python main.py --console
```

Sinov yoki demo uchun jonli kamera oynasi (landmark + scorelar overlay):

```bash
python main.py --visual
```

Chiziqlarsiz boshlash:

```bash
python main.py --visual -d
```

Hotkeylar:
- `d` debug chiziqlarni yoqadi/o'chiradi
- `i` info panelni yoqadi/o'chiradi
- `n` notificationlarni vaqtincha o'chiradi/yoqadi
- `h` hotkey panelini yashiradi/ko'rsatadi
- `ESC` yoki `q` oynani yopadi

Diagnostika uchun:

```bash
python main.py --doctor
```

Statistika report:

```bash
python main.py --stats
```

## Testlar

Stdlib `unittest` ishlatilgan, shuning uchun `pytest` shart emas.

```bash
python -m unittest discover -s tests -v
```

## Keyingi bosqichlar

- dimming / overlay nudge rejimi
- real tray ikonkalari va assetlar
- statistika dashboard yoki alohida settings oynasi
