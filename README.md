# Sri Lankan VAT Schedule 02 Checker

Check a Sri Lanka **VAT Schedule 02** file (input VAT, local purchases) before you upload it with your VAT return. The checker uses the same rules, in the same order, with the same messages as the Inland Revenue Department's **Schedule File Verifier v5.20**, so you get IRD's answer on any computer, including a Mac or a phone, without installing anything.

**Use it here: <https://harshawije.github.io/ird-vat-schedule-checker/>**

- Your file never leaves your device. The page reads it in the browser and sends nothing anywhere.
- It works offline: save [`index.html`](index.html) and open it from your computer.
- It tells you the right **period code**, and warns you when the code in the file name and the code you type disagree (IRD's tool doesn't).

> This is an unofficial tool. It is not made by, endorsed by or affiliated with the Inland Revenue Department of Sri Lanka. IRD can change its tool at any time. For a final check, run IRD's own Schedule File Verifier ([steps below](#check-with-irds-own-tool-windows-only)).

## Contents

- [How to use it](#how-to-use-it)
- [The period code](#the-period-code)
- [What IRD's tool accepts](#what-irds-tool-accepts)
- [Common errors and how to fix them](#common-errors-and-how-to-fix-them)
- [Check with IRD's own tool (Windows only)](#check-with-irds-own-tool-windows-only)
- [Use the checker in your own software](#use-the-checker-in-your-own-software)
- [How accurate is it?](#how-accurate-is-it)
- [Development](#development)
- [License](#license)

## How to use it

1. Open the [checker](https://harshawije.github.io/ird-vat-schedule-checker/).
2. Choose your `.csv` file, or drop it on the page. Pick the file exactly as you will upload it: IRD's tool checks the file name too.
3. Check the **period code**. The page fills it in from the file name. Use the year and month/quarter menus to work it out if you're unsure.
4. Read the result:
   - Green, **"This file passes IRD's checks"**: IRD's tool would show *Validation passed!*
   - Red, **"IRD's checker will reject this file"**: you see the message IRD's tool would show, the step where it stops, and a list of problems with the Serial No, the line in the file, the supplier, the invoice number and how to fix it.

IRD's tool stops at the first step that fails, and so does this checker. After you fix one batch of errors, check again: the next step may find more.

## The period code

Four digits: the last two digits of the year, the **calendar** quarter (1 to 4, where January to March is 1), then the month within that quarter (1 to 3), or 0 for the whole quarter. These are calendar quarters, not the April tax year.

| Quarter | Whole quarter | 1st month | 2nd month | 3rd month |
|---|---|---|---|---|
| Q1 | `2610` Jan–Mar 2026 | `2611` January | `2612` February | `2613` March |
| Q2 | `2620` Apr–Jun 2026 | `2621` April | `2622` May | `2623` June |
| Q3 | `2630` Jul–Sep 2026 | `2631` July | `2632` August | `2633` September |
| Q4 | `2640` Oct–Dec 2026 | `2641` October | `2642` November | `2643` December |

For another year, change the first two digits (2025 is `25…`). Only a single month or a single calendar quarter can be written as a code.

The code goes in two places: in the file name, and in the **Period code** box of IRD's tool. IRD's tool never checks that the two agree, so make sure they do. An empty box, or a code that isn't one of the above (such as `2603`), makes IRD's tool stop with an error.

## What IRD's tool accepts

### File name

```
{yourTIN}_VAT_SCHEDULE02_{periodcode}_{YYYYMMDD}_ORIGINAL_V{n}.csv
```

For example `100000016_VAT_SCHEDULE02_2640_20261119_ORIGINAL_V1.csv`.

- `yourTIN` is your own 9-digit TIN. It must have a valid check digit, or the tool says *"TIN number enter in name is invalid."*
- `YYYYMMDD` is the date you made the file.
- Upper or lower case doesn't matter.
- Nothing may be added. A browser that saves a second download as `… (1).csv` makes the name invalid: delete the old file first, or rename the new one.

### Contents

Plain CSV text (UTF-8; a byte-order mark is fine). Line 1 is this header:

```
Serial No,Invoice Date,Tax Invoice No,Supplier's TIN,Name of the Supplier,Description,Value of purchase,VAT Amount,Disallowed VAT Amount
```

Header names are matched ignoring case and the columns can be in any order, but there must be exactly these 9. Then one line per invoice. **No total row and no blank lines.**

IRD's tool splits each line on commas and knows nothing about quotes:

- A comma inside a supplier name or description breaks the file. In the first 10 lines you get *"Please make sure there are no 'commas' in the data and try again."*; after line 10 the columns shift and you get misleading errors. Remove commas from all text.
- Quotes are kept as part of the value, so don't put quotes around anything.
- A blank line, or a line with fewer fields, in the first 10 lines gives the same "commas" message.

| Column | Rule |
|---|---|
| Serial No | Whole number from 1, unique. `01` and `1` count as different. |
| Invoice Date | Month/day/year: `10/05/2026` or `10/5/2026`. Not after the end of the period. No earliest date. |
| Tax Invoice No | Up to 40 characters, only `A–Z a–z 0–9 _ / -`. No spaces, dots or `#`. The same invoice number (ignoring case) from the same supplier TIN twice is rejected. |
| Supplier's TIN | 9 digits with a valid check digit. Not your own TIN. Not the VAT-number form `xxxxxxxxx-7000`. |
| Name of the Supplier | Up to 100 characters. |
| Description | Up to 500 characters in the tool. IRD's Excel template says 50, so 50 is safer. |
| Value of purchase | Up to 2 decimals and 15 digits, no thousands separators, not negative. |
| VAT Amount | Up to 2 decimals. Must be within ±0.99 of value × VAT rate for the invoice date (see below). `0.00` always passes. |
| Disallowed VAT Amount | `0.00` when there is none; a blank fails. Not negative and not more than the VAT. |

VAT rates the tool accepts, by invoice date:

| Invoice date | Rate(s) accepted |
|---|---|
| From 1 Jan 2024 | 18% (15% also accepted up to 28 Jan 2024) |
| 1 Sep 2022 – 31 Dec 2023 | 15% (12% also accepted up to 28 Sep 2022) |
| 1 Jun 2022 – 31 Aug 2022 | 12% (8% also accepted up to 28 Jun 2022) |
| 29 Dec 2019 – 31 May 2022 | 8% |
| Before 29 Dec 2019 | 11% or 15% depending on the date; 5%, 7% and 8% are also accepted in parts of Nov 2018 – Dec 2019 |

The tool rounds value × rate to 2 decimals (half away from zero) and accepts a VAT figure up to 0.99 either side.

The tool checks in this order and stops at the first step that fails: **file name → reading the file → period code → columns and field formats → date format → business rules**. It lists at most 100 errors.

## Common errors and how to fix them

| IRD's message | What to do |
|---|---|
| Name of the file is incorrect. | Rename the file to the pattern above. Remove `(1)` or anything else a browser or person added. |
| TIN number enter in name is invalid. | The TIN at the start of the file name is wrong. Use your own TIN. |
| Please make sure there are no 'commas' in the data and try again. | Remove commas from names and descriptions. Remove blank lines. |
| Error : Input string was not in a correct format. | The Period code box is empty. Type the code. |
| Error : String reference not set to an instance of a String. | The period code isn't valid. Use a code from the table above. |
| Mandatory data not available. … RequiredFieldMissing | A field is empty. Use `0.00` for no disallowed VAT. If the Serial No is blank, you have a total row: delete it. |
| Maximum length of records exceeded. … Supplier's TIN | The TIN has `-7000` on the end. Use the 9-digit TIN only. |
| Data type mismatch. … 2 decimal places | Use at most 2 decimals and no thousands separators. |
| Date format is incorrect. | Write dates as month/day/year. Opening and saving the file in Excel often changes them. |
| Tax Invoice No entered is invalid. Please remove spaces. | Remove spaces from the invoice number (`Tec 662` → `Tec662`). |
| The invoice number contains invalid character(s). | Use only letters, digits, `_`, `/` and `-` (`10.01` → `10-01`). |
| Duplicated Tax Invoice from same supplier. | The same invoice number from this supplier appears twice. Check for a double entry. |
| Invoice date should not be after the end of the taxable period. | The invoice belongs to a later period, or the period code is wrong. |
| VAT amount should be equal to (value of purchase) * Vat rate … | VAT must be value × rate within 0.99. Check that the value excludes VAT, and that another tax (such as SSCL) is treated the same way the supplier's invoice treats it. Don't change the VAT figure to make it fit: fix the value or the record. |
| TIN is not valid. | The supplier's TIN check digit is wrong. Check it against the invoice. |
| Same TIN (indicated in schedule name) cannot be included as part of schedule record | A row uses your own TIN as the supplier. |
| The Schedule file is rejected due to unavailability of records. | The file has no invoice lines. |

## Check with IRD's own tool (Windows only)

1. Download **"Schedule File Verifier Tool"** (version 5.20) from [ird.gov.lk](https://www.ird.gov.lk) > Downloads > Tools. Unzip it and open `ScheduleFileVerifier.exe`.
2. Click **"VAT Schedule Verifier"**. File Type: **"VAT Schedule02"**.
3. Period code: type the code for your period. It must not be empty.
4. Browse: pick the `.csv` file. Don't open it in Excel and save it, because Excel changes dates and numbers. Don't rename it.
5. Click **Verify**. *"Validation passed!"* means you can upload it with the e-filing return. Otherwise the list shows the row (Serial Number) and the reason.

## Use the checker in your own software

The rules are available as a small library in two languages, with no dependencies. Both return the same result.

### JavaScript (browser or Node.js)

[`verifier.js`](verifier.js) works as a plain `<script>` (it defines `window.IRDVerifier`) or with `require`:

```js
const V = require('./verifier.js');
const bytes = new Uint8Array(fs.readFileSync(path));
const r = V.verify(fileName, bytes, '2640');
// r.passed  true / false
// r.stage   'filename' | 'basic' | 'special' | 'exception' | 'done'
// r.popup   the message IRD's tool would show
// r.errors  [{ serial, message }]  the list under it
// r.rows    the parsed rows, so you can link an error back to a line

V.periodCodeFor(2026, [10, 11, 12]);   // '2640'
V.periodCodeDates('2641');            // [20261001, 20261031]
V.tinIsValid('100000016');            // true
V.fileNameFor('100000016', '2640', new Date());
```

### Python 3 (standard library only)

[`python/ird_schedule_verifier.py`](python/ird_schedule_verifier.py):

```python
import ird_schedule_verifier as v

result = v.verify(file_name, content_bytes, '2640')
v.period_code_for(2026, [10, 11, 12])   # '2640'
v.period_code_dates('2641')             # (date(2026, 10, 1), date(2026, 10, 31))
v.tin_is_valid('100000016')             # True
v.file_name_for('100000016', '2640', date.today())
```

If you generate the file yourself, strip commas, double quotes and line breaks from every text value, write dates as `%m/%d/%Y`, write amounts with 2 decimals, write `0.00` for no disallowed VAT, add no total row, and run `verify()` on the exact bytes you will hand to the user.

## How accurate is it?

The rules were reverse-engineered from IRD's Schedule File Verifier v5.20 and its libraries, and ported to Python. The Python port gives the same result as the real tool on **122 test files**: 117 cases covering every rule and quirk, plus 5 real schedules.

The JavaScript port in this repository gives the same result as the Python port on the 40 reference cases in [`tests/cases.json`](tests/cases.json) (each carries the real tool's answer) and on 30,000 randomly generated awkward files ([`tools/fuzz.py`](tools/fuzz.py)).

Known differences:

- If the period part of the file name contains a character such as a bracket, the error text differs from the .NET wording. Either way the file fails.
- An Invoice Date made only of spaces: the checker reports "Invoice Date could not be read." (the Python port stops with an exception).

The quirks are kept on purpose, because the point is to give IRD's answer. For example, a VAT Amount of `0.00` always passes, and a file name with a different period code from the box still passes.

## Development

No build tools are needed to use the page. To change it:

```bash
npm test               # JavaScript and Python tests
node tools/build.js    # rebuild index.html after editing verifier.js or tools/page.html
python3 tools/fuzz.py 1 5000 > /tmp/fz.json   # random files for comparing the two ports
```

- [`verifier.js`](verifier.js): the rules (JavaScript).
- [`python/ird_schedule_verifier.py`](python/ird_schedule_verifier.py): the rules (Python).
- [`tools/page.html`](tools/page.html): the page; `tools/build.js` inlines `verifier.js` into it to make the single-file [`index.html`](index.html).
- [`tests/`](tests): reference cases and tests. Regenerate the cases with `python3 tests/make_cases.py 100000016 > tests/cases.json`.

When IRD releases a new verifier version, update both ports together and add a case to `tests/make_cases.py` for each change, with the real tool's answer.

The TINs in the examples and tests (such as `100000016` and `100000024`) are made-up numbers that pass the check digit. They don't belong to anyone.

## License

[MIT](LICENSE). Use it, change it and share it freely. There is no warranty: you remain responsible for what you file with IRD.
