# 🎬 Torbgard — 5-minute demo script

**Format:** screen recording of a phone (or a narrow browser window ~390 px), Persian voice-over.
**Goal:** in five minutes a judge must see the full loop *and* the honesty rules, not a feature list.

> Before recording, freeze the clock so shops are open at a realistic hour:
> `DEMO_NOW=2026-10-21T17:30:00+03:30 make serve` (a Wednesday evening).
> Seller replies still use real time, so the contact beat stays dynamic.

Run `python scripts/seed_demo.py` and paste its output into the notes below — it prints the exact
product id, the four shops, which one answers and which one stays silent.

---

## 0:00 — 0:20 · The hook (home screen)

> «ترب به ما می‌گوید یک محصول چند است. ولی وقتی می‌خواهیم **حضوری** بخریم، سه سؤال بی‌جواب
> می‌ماند: کدام مغازه؟ الان باز است؟ و این قیمت هنوز واقعی است؟ ترب‌گرد همین را جواب می‌دهد.»

Show the home screen, tap the location chip («موقعیت من» → allow), then point at the sentence under
the search box: «قیمت‌ها ثبت‌شده‌اند؛ قبل از رفتن، از فروشنده بپرسید.»

## 0:20 — 0:50 · One sentence → three models

Type **«هدفون بلوتوثی زیر ۳ میلیون»** (or tap the suggestion). On the results screen:

* Sort chips: **بهترین ترکیب / ارزان‌ترین / نزدیک‌ترین / مطمئن‌ترین**.
* Tap a card → the trade-off sheet: price range, specs the dataset actually knows, and «نامشخص»
  for the ones it doesn't.

> «هیچ مشخصاتی از خودمان نمی‌سازیم؛ هر چیزی که در دیتاست نباشد، نامشخص می‌ماند.»

## 0:50 — 1:30 · Wrong-price protection

Tap the most expensive card → the small print under the price: **«ثبت‌شده ۳ ماه پیش»** in amber.

> «این قیمت کهنه است. ترب‌گرد قیمت را با تاریخش نشان می‌دهد، نه به‌تنهایی.»

## 1:30 — 2:20 · Shops near me (the core screen)

Open a product, tap **فروشگاه‌ها**. Show:

1. the stats strip (تعداد، ارزان‌ترین، نزدیک‌ترین)،
2. one card whose price is «۲٫۴ میلیون» with a green **باز در زمان رسیدن** and a walk time,
3. one card with **بسته در زمان رسیدن** — tap «فقط باز الان» and watch it disappear,
4. open **فیلترها** → turn on «قسطی تأییدشده» → the sheet explains it is a *hard* filter.

> «فاصله با هاورساین حساب می‌شود، چون به هیچ کلید مسیریابی وابسته نیستیم.»

## 2:20 — 2:50 · Compare stores

Select 3 shops → **مقایسه**. Point at the highlighted cheapest row, the «ساعت کاری در زمان رسیدن»
row, and the installment row where two shops say **نامشخص** — the app refuses to guess.

## 2:50 — 3:10 · Inside the mall

Open the shop in «پاساژ نگین» → **راهنمای مسیر داخل پاساژ**:

> «پاساژ نگین، طبقه زیرزمین، واحد ۲۸۵ — اطمینان ۹۰٪»

Show the copy button and the ask-sentence.

## 3:10 — 3:55 · Ask the seller (the money shot)

Tap **پرسش قیمت و موجودی**. The contact sheet opens with the «شبیه‌سازی» badge and the honest note.

1. The message is pre-filled; send it.
2. The timeline moves: ارسال شد → دیده شد → پاسخ آمد.
3. The reply arrives: **«قیمت فعلی ۲۴٬۲۱۰٬۰۰۰ تومان است (قیمت ثبت‌شده ۲۵٬۳۱۰٬۰۰۰ تومان بود). موجود داریم.»**
4. The parsed chips show **موجود** and **قیمت تأییدشده ۲۴٬۲۱۰٬۰۰۰**; the card turns green.

> «این تفاوت یک میلیون و صد هزار تومانی، همان دلیلی است که باید پرسید.»

## 3:55 — 4:25 · Silence is an answer too

Open a second shop that stays silent (the seed script names it). Send, wait ~15 s.

* The thread flips to **«پاسخ نداد»** with a red tone.
* The alternatives sheet slides up: «همین محصول در ۳ فروشگاه دیگر» + «مدل‌های مشابه» — one tap goes back
  to the store list with those pins.

> «وقتی جواب نمی‌آید، به کاربر نمی‌گوییم صبر کن؛ جایگزین می‌دهیم.»

## 4:25 — 4:40 · The plan

Tap **برنامه سفر**: ordered stops with arrival time, «این مغازه ساعت ۲۰:۰۰ می‌بندد» warning,
«باز کردن در نقشه» and «کپی».

## 4:40 — 4:55 · The agent (one sentence, no typing beyond one line)

Open **دستیار** (center button). Type:
**«گوشی سامسونگ تا ۲۰ میلیون قسطی، نزدیک ونک»**

Show the tool trace chips (جست‌وجوی محصول، یافتن فروشگاه …), then product and store cards inline.
Point at the small line «منبع: دیتاست ترب، اسنپ‌شات ۲۰۲۶-۱۰-۱۳» under the answer.

> «دستیار فقط انتخاب می‌کند؛ اعداد از ابزارها می‌آیند و هر جمله‌ای که عدد بی‌سند داشته باشد حذف می‌شود.»

## 4:55 — 5:00 · Close

> «ترب‌گرد جواب یک سؤال است: **آیا ارزش دارد برای این محصول، الان، به این مغازه بروم؟**»

End on the plan screen.

---

## Recording checklist

- [ ] `DEMO_NOW` set to a weekday evening (otherwise many shops are closed and the demo looks empty)
- [ ] `make data` rebuilt **after** any ETL change (the DB is prebuilt)
- [ ] `scripts/seed_demo.py` output pasted here with the chosen product
- [ ] LLM key set **or** decide to show the deterministic mode on purpose (the UI labels it)
- [ ] browser at 100 % zoom, 390×844, Persian keyboard
- [ ] notifications off, other tabs closed
- [ ] one silent shop and one answering shop identified in advance
- [ ] the «شبیه‌سازی» badge is visible in the contact shot (it must not be cropped)

## Fallbacks

| If… | Then |
|---|---|
| the LLM is slow or has no key | stay in deterministic mode and say: «همین مسیر بدون مدل هم کامل کار می‌کند» |
| a seller answers too fast to film | raise `CONTACT_TIMEOUT_SECONDS` or re-open the thread |
| the map tiles are blocked | switch to the list — distance and hours are independent of tiles |
| a shop chosen in advance behaves differently | `scripts/seed_demo.py` prints a second candidate |
| someone asks about real data | show `/api/meta` → `dataset_mode` and the «داده‌ی نمایشی» badge |

## What the five minutes must prove

1. price ≠ truth → date + availability are always adjacent
2. open/closed is computed **at arrival**, and unknown is labelled
3. installment is evidence-based, not decoration
4. in-mall guidance is specific (floor/unit) or explicitly low-confidence
5. contact → confirmed price/stock, or timeout → alternatives
6. a plan the user can execute
7. the agent is a shortcut, not a wall: every action exists as a button
