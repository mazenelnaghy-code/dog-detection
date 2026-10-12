<div dir="rtl">

# البداية: من الصفر لحد جهاز شغال

([English](GETTING_STARTED.md))

الدليل ده بيمشي معاك في كل حاجة بالترتيب. مش لازم تكون مبرمج: انسخ الأوامر زي ما هي. كل خطوة بتنتهي
بـ ✅ **فحص**؛ ما تكمّلش غير لما الفحص ينجح.

| الخطوة | إيه | الوقت | محتاج هاردوير؟ |
|---|---|---|---|
| 1 | جرّبه على الكمبيوتر | 15 دقيقة | لا |
| 2 | اشتري القطع | – | – |
| 3 | جهّز كارت الذاكرة للراسبيري | 20 دقيقة | راسبيري + كارت |
| 4 | سطّب البرنامج على الراسبيري | 30–60 دقيقة | راسبيري |
| 5 | وصّل الهاردوير | ساعة | كل حاجة |
| 6 | ركّبه في المكان واظبطه | 1–3 أيام | كل حاجة |
| 7 | الاستخدام اليومي والتحديث | – | – |

---

## 1. جرّبه على الكمبيوتر

1. سطّب **Python 3.10 أو أحدث** من [python.org](https://www.python.org/downloads/).
   على ويندوز علّم على **"Add python.exe to PATH"** في التسطيب.
2. سطّب **Git** من [git-scm.com](https://git-scm.com/downloads).
3. افتح Terminal (ويندوز: *Command Prompt*، ماك/لينكس: *Terminal*) واكتب:

```bash
git clone https://github.com/mazenelnaghy-code/dog-detection.git
cd dog-detection
python -m venv .venv
```

فعّل البيئة (كل مرة تفتح Terminal جديد):

| ويندوز | ماك / لينكس |
|---|---|
| `.venv\Scripts\activate` | `source .venv/bin/activate` |

```bash
pip install -r requirements.txt
pip install --no-deps -e .
python -m dog_repeller --demo
```

✅ **فحص:** هتفتح نافذة فيديو. أطفال وقطة بيعدّوا من غير إنذار، وبعدين كلب بيقرب، واللوج بيكتب
`BUZZER -> beep` و `ULTRASONIC REPELLER -> ON`، وبعدين النظام بيهدى. افتح **http://127.0.0.1:8000** في
المتصفح عشان تشوف لوحة التحكم. دوس `q` للخروج.

مش عايز تسطّب حاجة خالص؟ استخدم
[نوتبوك Colab](https://colab.research.google.com/github/mazenelnaghy-code/dog-detection/blob/main/notebooks/demo_colab.ipynb)
من المتصفح.

## 2. اشتري القطع

القائمة الكاملة ونصايح الاختيار في [HARDWARE.md](HARDWARE.md). باختصار: راسبيري باي 5 (أو 4)، وكارت
micro-SD سعة 32 جيجا، وكاميرا راسبيري (NoIR للّيل)، وشاشة HDMI مقاس 7 بوصة، وموديول ريلاي قناة واحدة،
وموديول بازر Active، وجهاز طرد كلاب بالموجات فوق الصوتية 12 فولت على تردد 23 كيلوهرتز أو أكتر، ومحوّل 12 فولت،
وشاحن الراسبيري الرسمي، ومروحة، وأسلاك توصيل، وعلبة للجهاز.

## 3. جهّز كارت الذاكرة للراسبيري

1. على الكمبيوتر سطّب **Raspberry Pi Imager** من [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. اختار **الجهاز** (Pi 4 أو Pi 5)، والنظام **Raspberry Pi OS (64-bit)**، وكارت الذاكرة.
3. قبل الكتابة دوس **Edit settings** (OS customisation):
   - اسم الجهاز (hostname): `dogguard`
   - اسم مستخدم وباسورد: اختارهم انت (هتحتاجهم)
   - Wi-Fi: اسم الشبكة والباسورد والدولة
   - في تبويب Services: فعّل **SSH** (بالباسورد)
4. اكتب الكارت، وحطه في الراسبيري، ووصّل الشاشة والباور، واستنى حوالي دقيقتين.

✅ **فحص:** من الكمبيوتر، الأمر `ssh <اسم-المستخدم>@dogguard.local` بيدخّلك على الراسبيري. ولو الشاشة
والكيبورد والماوس متوصلين، ممكن تستخدم Terminal من سطح المكتب على الراسبيري.

## 4. سطّب البرنامج على الراسبيري

وصّل الكاميرا الأول لو معاك (شوف [WIRING.ar.md، الخطوة 2](WIRING.ar.md))، والباور مفصول. بعدين على الراسبيري:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/mazenelnaghy-code/dog-detection.git ~/dog-detection
cd ~/dog-detection
bash deploy/setup_pi.sh            # أو: bash deploy/setup_pi.sh desktop  (الفيديو على شاشة HDMI)
```

شغّله باليوزر العادي، **مش** بـ `sudo`؛ هو هيطلب الباسورد لما يحتاج. أول مرة بياخد من 30 لـ 60 دقيقة.
في الآخر هيطبع **لينك لوحة التحكم**، زي `http://192.168.1.50:8000/?token=…`. احتفظ بيه، لأن الـ token هو الباسورد.

✅ **فحص:** افتح اللينك على موبايلك (على نفس الـ Wi-Fi). هتشوف الكاميرا مباشر والحالة **ARMED**. لو لسه مفيش
كاميرا متوصلة، الخدمة هتعيد تشغيل نفسها كل كام ثانية، وده طبيعي لحد الخطوة 5.

## 5. وصّل الهاردوير

امشي على [WIRING.ar.md](WIRING.ar.md): فيه رسمة و7 خطوات قصيرة، وكل خطوة ليها فحص. **افصل كل الكهربا قبل
ما تلمس أي سلك.**

بعد ما تخلّص، شغّل الفحص الذاتي:

```bash
cd ~/dog-detection
.venv/bin/python tools/hardware_check.py --config config/local.yaml
```

✅ **فحص:** كل سطر مكتوب جنبه **PASS** (اكتب `y` لما تسمع البازر وتكّة الريلاي)، وفي الآخر `ALL GOOD`.

## 6. ركّبه في المكان واظبطه

ثبّت الكاميرا في مكانها النهائي وخليها باصة على المكان اللي الكلاب بتيجي منه (بوابة، سور، مدخل الملعب).
وبعدين امشي على [دليل الاختبار](TESTING.ar.md)، المرحلتين 2 و 3:

1. **مراقبة بس** يوم أو أكتر: سيب جهاز الطرد مفصول أو خلّي `hardware.backend: sim`.
2. **ارسم منطقة الخطر** على الصورة الحقيقية:
   `.venv/bin/python tools/set_zone.py --config config/local.yaml --write`
   (محتاج سطح مكتب الراسبيري؛ لو شغال SSH بس، عدّل `zone.rect` في `config/local.yaml` بإيدك).
3. راجع اللوج: فيه كلاب ما اتكشفتش؟ فيه إنذارات غلط؟ واظبط على حسب ده.
4. **شغّله** في وجود المشرفين، بعد ما تتأكد إن جهاز الطرد على تردد 23 كيلوهرتز أو أكتر.

بعد أي تعديل في الإعدادات: `sudo systemctl restart dog-repeller`.

## 7. الاستخدام اليومي والتحديث

| عايز… | اعمل كده |
|---|---|
| أشوف اللي بيحصل | افتح لينك لوحة التحكم من موبايل أو كمبيوتر على نفس الـ Wi-Fi |
| أوقفه شوية | لوحة التحكم ← **Disarm** (وبعدين **Arm** تاني) |
| أجرّب جهاز الطرد | لوحة التحكم ← **Test repeller** |
| أشوف اللوج | `journalctl -u dog-repeller -f` |
| أغيّر إعداد | عدّل `config/local.yaml` (بيغطي على `config/pi.yaml`) وبعدين restart |
| أحدّث لآخر نسخة | `cd ~/dog-detection && git pull && sudo systemctl restart dog-repeller` |
| أفحص الهاردوير | `.venv/bin/python tools/hardware_check.py --config config/local.yaml` |

إعداداتك في `config/local.yaml` (ومعاها باسورد لوحة التحكم) عمرها ما بتتمسح بـ `git pull`.

**فيه مشكلة؟** شوف جدول المشاكل في الـ [README](../README.ar.md)، أو افتح Issue على GitHub ومعاه نتيجة
`tools/hardware_check.py`.

</div>
