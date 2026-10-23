# Demo script — 5 minutes, one phone, no instructions needed

**Record in Persian. Screen-record a phone (or the mobile viewport), portrait.**
Two rules: never read a slide while an app screen is available, and never claim something the
screen does not show.

Seed state before recording (2 minutes, do it once):

```bash
make synthetic && make data && make build && make serve
# open http://localhost:8000 in a phone-sized window, choose «شیخ هادی» as neighbourhood
# (or tap «موقعیت من»), and pin the app to the home screen to show the PWA.
```

Time cues assume `CONTACT_TIMEOUT_SECONDS=45` and `DEMO_TIME_SCALE=20`.

---

## 0:00 – 0:25 · The gap (voice-over, home screen)

> «ترب قیمت آنلاین را نشان می‌دهد. ولی وقتی تصمیم می‌گیریم **حضوری** بخریم، سه سؤال بی‌جواب می‌ماند:
> این مغازه الان باز است؟ این قیمت هنوز واقعی است؟ و اگر جواب نداد، کجا بروم؟»

Show the home screen: search box «چی می‌خوای بخری؟», sample queries, the chips
«فقط فروشگاه‌های باز الان» / «همه فروشگاه‌ها» / «فقط فروشگاه‌های اقساطی تأییدشده».
Point at the badge **«داده‌ی نمایشی (ساختار واقعی دیتاست)»**.

## 0:25 – 1:10 · From a sentence to three models

Tap the suggestion **«هدفون بلوتوثی زیر ۳ میلیون»** → results screen.

* Sort chips: «بهترین ترکیب»، «ارزان‌ترین»، «نزدیک‌ترین»، «مطمئن‌ترین».
* Each card: price **+ age** + availability, e.g. «۲٬۴۵۰٬۰۰۰ تومان — ۱۲ روز پیش — موجودی نامشخص».
* Select two products → **مقایسه** (specs table; unknown cells say «نامشخص»).

Voice-over the rule: «هیچ‌جا قیمت بدون تاریخ و وضعیت موجودی نمی‌بینید.»

## 1:10 – 2:00 · Shops near me (this is the core)

Tap a model → **فروشگاه‌ها**.

* Stats strip: count, cheapest, nearest.
* List shows distance, walk time, open/closed at arrival, installment badge.
* Toggle **نقشه**: price pins on OSM tiles; tap a pin → shop popup.
* Open **فیلترها**: radius, max price, «باز الان», «اقساطی» (hard filter, with the note
  «فروشگاه بدون ارائه‌دهنده کنار گذاشته می‌شود»).

Say: «قسطی فقط وقتی نشان داده می‌شود که دادهٔ پرداخت مغازه واقعاً اقساط حضوری داشته باشد؛
محدودیت ۰/۰ یعنی نامشخص، نه بی‌نهایت.»

## 2:00 – 2:40 · Compare, then look inside one shop

* Select 3 shops → **مقایسه** table: price, distance, hours, warranty, installment, address confidence.
* Open one shop → **جزئیات فروشگاه**:
  * status strip (open at ETA / unknown),
  * score breakdown bars (why this shop is #1),
  * **راهنمای داخل پاساژ**: floor/unit/landmark + «اطمینان آدرس» + a ready-to-say sentence,
  * weekly hours sheet, contacts.

## 2:40 – 3:40 · Ask the seller (the money moment)

Tap **تماس با فروشنده**.

* Badge **شبیه‌سازی** is visible; the notice explains that numbers are demo and real channels
  (تماس / واتس‌اپ / بله) are one tap away.
* Send the prefilled question «قیمت و موجودی همین مدل رو دارید؟».
* Watch the stepper: ارسال شد → دیده شد → پاسخ آمد → **تأیید شد** (or **ناموجود** / **پاسخ نداد**).
* Parsed answer grid: موجودی، قیمت تأییدشده، ساعت — anything unknown says «نامشخص».

Second thread to show the failure path (pick a shop with stale price): no reply → after the
timeout the card turns into **«فروشنده پاسخ نداد»** with 3 automatic alternatives.

## 3:40 – 4:15 · Alternatives and the trip plan

* From the alternatives card, open one → back to store detail.
* Tap **برنامه سفر** (bottom nav «سفر»): numbered stops with times, warnings («این مغازه ساعت ۲۱
  بسته می‌شود»), **باز کردن در نقشه** (Google Maps deep link), **کپی**.

## 4:15 – 4:45 · The agent, in one sentence

Tap the center FAB **دستیار**. Type:

> «گوشی سامسونگ تا ۲۰ میلیون قسطی، نزدیک ونک»

* Tool trace appears («جست‌وجوی محصول»، «یافتن فروشگاه»…), then product and store cards.
* Tap a card → the agent navigates the same screens (chat is an accelerator, not a wall).

If no LLM key is configured the header shows «حالت بدون مدل زبانی» — say it out loud:
«بدون کلید هم همه‌ی این مسیر کار می‌کند؛ مدل فقط جمله‌بندی را بهتر می‌کند، داده را نمی‌سازد.»

## 4:45 – 5:00 · Close

> «ترب‌گرد قیمت را به تصمیم تبدیل می‌کند: کدام مدل، کدام مغازه، الان باز است یا نه، و اگر جواب
> نداد چه کنیم. هر عدد از داده می‌آید؛ هر چیزی که نمی‌دانیم، نامشخص می‌ماند.»

End on the home screen with the badge visible.

---

## Backup scenarios (if the live demo misbehaves)

| Situation | Do this instead |
|---|---|
| LLM slow / no key | stay in degraded mode — the UI already labels it |
| Map tiles blocked | switch to **لیست**; say «نقشه اختیاری است، دادهٔ فاصله از مختصات است» |
| Seller replies too fast | raise `CONTACT_TIMEOUT_SECONDS` to 60 and re-record that beat |
| A product has only stale prices | that is the point — show «قیمت کهنه» and the contact flow |
| Search term unknown | use the three home suggestions; they are seeded and tested |

## Shot list (for the editor)

1. Home (badge + suggestions) — 5 s
2. Search → results with price/age/availability — 8 s
3. Product compare — 5 s
4. Shops list — 6 s
5. Map + pin popup — 6 s
6. Filters sheet (installment) — 5 s
7. Store detail: status strip + score bars — 7 s
8. In-mall guide + copy — 5 s
9. Contact: stepper → confirmed — 10 s
10. Contact: timeout → alternatives — 8 s
11. Plan screen — 7 s
12. Agent chat with tool trace — 8 s
13. Home close — 5 s

## What must be on screen at some point

- [ ] price **with** date and availability
- [ ] «نامشخص» used for a genuinely unknown fact
- [ ] a shop that is **closed at arrival**
- [ ] installment filter excluding a shop
- [ ] a simulated contact with the badge
- [ ] a timeout with automatic alternatives
- [ ] in-mall floor/unit guidance
- [ ] visit plan
- [ ] the agent calling tools
