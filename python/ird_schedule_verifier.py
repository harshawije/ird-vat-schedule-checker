"""
A Python port of the IRD's "Schedule File Verifier" (v5.20) for
VAT Schedule 02 (input VAT, local purchases), file type 22032.

Reverse-engineered from ScheduleFileVerifier.exe and its libraries, and
checked case by case against the real engine. Same order, same rules,
same messages, including its quirks:

  1. File name    the TIN check digit and the name pattern
  2. Read CSV     plain comma split, no quotes
  3. Period code  must be a number (the tool does Convert.ToInt32 on it)
  4. Basic        column names, required / type / length / 2-dp decimals
  5. Dates        Invoice Date must be M/d/yyyy
  6. Special      duplicate serials, then the Schedule 02 business rules

verify(file_name, content_bytes, period_code) -> dict:
    passed  bool
    stage   'filename' | 'basic' | 'special' | 'exception' | 'done'
    popup   the message box text the tool would show
    errors  [{'serial': str, 'message': str}]   the grid under it

Standard library only.
"""
import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MAX_ERRORS = 100
COLUMNS = [
    ('Serial No', 'int', 10),
    ('Invoice Date', 'str', None),
    ('Tax Invoice No', 'str', 40),
    ("Supplier's TIN", 'str', 9),
    ('Name of the Supplier', 'str', 100),
    ('Description', 'str', 500),
    ('Value of purchase', 'dec', 15),
    ('VAT Amount', 'dec', 15),
    ('Disallowed VAT Amount', 'dec', 15),
]
FILE_NAME_FORMAT = r'{0}_VAT_SCHEDULE02_{1}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_ORIGINAL_V(\d+).CSV'

CODE_HEADER = {
    'F001': 'File schema mismatch.',
    'F002': 'Mandatory data not available.',
    'F003': 'Data type mismatch.',
    'F004': 'Data type mismatch.',
    'F005': 'Maximum length of records exceeded.',
    'S616': 'The Schedule file is rejected due to unavailability of records.',
}
NO_RECORDS = 'The Schedule file is rejected due to unavailability of records.'
COMMAS_POPUP = "Please make sure there are no 'commas' in the data and try again."
TOO_MANY = '\r\nToo many errors to show. Maximum is 100'

D = lambda m, d, y: date(y, m, d)  # noqa: E731
VAT_DATES = dict(
    d1=D(5, 1, 2016), d2=D(7, 12, 2016), d3=D(11, 1, 2016), d4=D(11, 1, 2018),
    d5=D(6, 1, 2019), d6=D(12, 29, 2019), d7=D(12, 1, 2019), d7e=D(6, 28, 2022),
    d8=D(6, 1, 2022), d8e=D(9, 28, 2022), d9=D(9, 1, 2022), d9e=D(1, 28, 2024),
    d10=D(1, 1, 2024),
)
R1, R2, R3, R4, R5, R6, R7, R8 = (Decimal(x) for x in
                                  ('0.11', '0.15', '0.05', '0.07', '0.08', '0.12', '0.15', '0.18'))


class _Fail(Exception):
    pass


_INT_RE = re.compile(r'^\s*[+-]?\d+\s*$')
_DEC_RE = re.compile(r'^\s*[+-]?(\d[\d,]*)?(\.\d*)?[+-]?\s*$')


def _int32(text):
    if not _INT_RE.match(text):
        return None
    value = int(text.strip())
    return value if -2**31 <= value < 2**31 else None


def _int32_converter_ok(text):
    t = text.strip()
    for prefix in ('0x', '0X', '&h', '&H', '#'):
        if t.startswith(prefix):
            try:
                v = int(t[len(prefix):], 16)
            except ValueError:
                return False
            return v < 2**32
    return _int32(text) is not None


def _decimal(text):
    if not _DEC_RE.match(text) or not re.search(r'\d', text):
        return None
    t = text.strip()
    sign = 1
    if t[:1] in '+-':
        sign, t = (-1 if t[0] == '-' else 1), t[1:]
    elif t[-1:] in '+-':
        if t[-1] == '-':
            sign = -1
        t = t[:-1]
    t = t.replace(',', '')
    if t.startswith('.'):
        t = '0' + t
    if t.endswith('.'):
        t = t[:-1]
    try:
        return sign * Decimal(t)
    except InvalidOperation:
        return None


_FLOAT_RE = re.compile(r'^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\s*$')


def _decimal_converter_ok(text):
    if not _FLOAT_RE.match(text):
        return False
    try:
        return abs(Decimal(text.strip())) < Decimal('79228162514264337593543950336')
    except InvalidOperation:
        return False


def _round2(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


_DATE_RE = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})$')


def _parse_mdy(text):
    m = _DATE_RE.match(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def tin_is_valid(tin):
    if len(tin) != 9 or not all(c in '0123456789' for c in tin):
        return False
    d = [int(c) for c in tin]
    s = 3 * d[0] + 2 * d[1] + sum(d[j - 1] * (10 - j) for j in range(3, 9))
    check = 11 - s % 11
    if check in (10, 11):
        check = 0
    if check == d[8]:
        return True
    return 149000001 <= int(tin) <= 149002622


def period_code_dates(code):
    if not re.fullmatch(r'[0-9]{2}[1-4][0-3]', code or ''):
        return None
    year, quarter, month = 2000 + int(code[:2]), int(code[2]), int(code[3])
    if month == 0:
        first = (quarter - 1) * 3 + 1
        last = first + 2
    else:
        first = last = (quarter - 1) * 3 + month
    return date(year, first, 1), date(year, last, calendar.monthrange(year, last)[1])


def period_code_for(year, months):
    months = sorted(months)
    quarter = (months[0] - 1) // 3 + 1
    if len(months) == 1:
        return f'{year % 100:02d}{quarter}{(months[0] - 1) % 3 + 1}'
    if months == [(quarter - 1) * 3 + 1, (quarter - 1) * 3 + 2, (quarter - 1) * 3 + 3]:
        return f'{year % 100:02d}{quarter}0'
    raise ValueError('IRD period codes are one month or one calendar quarter')


def file_name_for(own_tin, code, made_on, version=1):
    return f'{own_tin}_VAT_SCHEDULE02_{code}_{made_on:%Y%m%d}_ORIGINAL_V{version}.csv'


def _check_file_name(name):
    parts = name.split('_')
    if len(parts) < 4:
        raise _Fail('Index was outside the bounds of the array.')
    tin_ok = tin_is_valid(parts[0])
    pattern = FILE_NAME_FORMAT.format(parts[0].strip(), parts[3])
    if not tin_ok:
        return 'TIN number enter in name is invalid.'
    try:
        matched = re.search(pattern, name.upper().strip())
    except re.error as e:
        raise _Fail(str(e))
    if not matched or len(parts[3]) != 4:
        return 'Name of the file is incorrect.'
    if len(parts) < 5:
        raise _Fail('Index was outside the bounds of the array.')
    if len(parts[4]) != 8:
        return 'Name of the file is incorrect.'
    return None


def _decode(content):
    for bom, enc in ((b'\xef\xbb\xbf', 'utf-8'), (b'\xff\xfe\x00\x00', 'utf-32-le'),
                     (b'\x00\x00\xfe\xff', 'utf-32-be'), (b'\xff\xfe', 'utf-16-le'),
                     (b'\xfe\xff', 'utf-16-be')):
        if content.startswith(bom):
            return content[len(bom):].decode(enc, errors='replace')
    return content.decode('utf-8', errors='replace')


def _read_table(content):
    text = _decode(content)
    lines = re.split(r'\r\n|\r|\n', text)
    if lines and lines[-1] == '':
        lines.pop()
    if not lines:
        raise _Fail('FileEmpty')

    sample, count, chosen = lines[:10], None, False
    i = 0
    while i < len(sample) and ',' in sample[i]:
        n = len(sample[i].split(','))
        if count is None:
            count = n
        elif n != count:
            break
        i += 1
    else:
        chosen = i == len(sample)
    split = (lambda s: s.split(',')) if chosen else (lambda s: re.split(r'\s', s))

    header = [h.lower().strip() for h in split(lines[0])]
    names, seen = [], set()
    auto = 1
    for h in header:
        if h == '':
            while f'column{auto}' in seen:
                auto += 1
            h = f'column{auto}'
        if h in seen:
            raise _Fail('__DUPLICATE__')
        seen.add(h)
        names.append(h)

    rows = []
    for line in lines[1:]:
        fields = split(line)
        if not any(f != '' for f in fields):
            continue
        row = {n: '' for n in names}
        for k, f in enumerate(fields[:len(names)]):
            row[names[k]] = f
        rows.append(row)
    return names, rows


def _basic(names, rows):
    errors, codes = [], []

    missing = [c for c, _, _ in COLUMNS if c.lower() not in names]
    if missing:
        return 'File schema mismatch.,', [
            {'serial': 'NA', 'message': f"Column '{c}' is required based on the file specification."}
            for c in missing]
    if not rows:
        return CODE_HEADER['S616'] + ',', [{'serial': 'NA', 'message': NO_RECORDS}]

    failing = 0
    for row in rows:
        row_errors = []
        for col, kind, length in COLUMNS:
            v = row[col.lower()]
            code, msg = None, None
            if v == '':
                code, msg = 'F002', 'RequiredFieldMissing'
            elif kind == 'int' and not _int32_converter_ok(v):
                code, msg = 'F003', 'InvalidDataType'
            elif kind == 'dec' and not _decimal_converter_ok(v):
                code, msg = 'F003', 'InvalidDataType'
            elif kind == 'dec':
                parsed = _decimal(v)
                if (len(v.replace('.', '')) > length or parsed is None
                        or _round2(parsed) != parsed):
                    code, msg = 'F004', f'Decimal value require {length} digit and 2 decimal places.'
            elif length is not None and len(v) > length:
                code, msg = 'F005', 'InvalidStringLength'
            if code:
                row_errors.append((code, f"Column '{col}' with data '{v}' failed on validation due to {msg}."))
        if row_errors:
            failing += 1
            for code in dict.fromkeys(c for c, _ in row_errors):
                if code not in codes:
                    codes.append(code)
            errors += [{'serial': row['serial no'], 'message': m} for _, m in row_errors]
        if failing >= MAX_ERRORS:
            break
    if errors:
        return ''.join(CODE_HEADER[c] + ',' for c in codes), errors

    date_errors = [{'serial': row['serial no'], 'message': 'Date format is not correct in Invoice Date'}
                   for row in rows
                   if row['invoice date'].strip() and _parse_mdy(row['invoice date'].strip()) is None]
    if date_errors:
        return 'Date format is incorrect.', date_errors
    return None, []


def _rates(d):
    v = VAT_DATES
    rate = b1 = b2 = rate2 = Decimal(0)
    if d <= v['d1']:
        rate = R1
    elif v['d1'] < d < v['d2']:
        rate = R2
    elif v['d2'] <= d < v['d3']:
        rate = R1
    elif v['d3'] <= d < v['d4']:
        rate = R2
    elif v['d4'] <= d < v['d5']:
        rate, rate2 = R2, R3
    elif v['d5'] <= d < v['d7']:
        rate, rate2, b1 = R2, R3, R4
    elif v['d7'] <= d < v['d6']:
        rate, rate2, b1, b2 = R2, R3, R4, R5
    elif v['d6'] <= d < v['d8']:
        rate = R5
    elif v['d8'] <= d <= v['d7e']:
        rate, rate2 = R5, R6
    elif v['d8'] <= d < v['d9']:
        rate = R6
    elif v['d9'] <= d <= v['d8e']:
        rate, rate2 = R6, R7
    elif v['d9'] <= d < v['d10']:
        rate = R7
    elif v['d10'] <= d <= v['d9e']:
        rate, rate2 = R7, R8
    elif d >= v['d10']:
        rate = R8
    return rate, b1, b2, rate2


def _within(vat, value, rate):
    centre = _round2(rate * value)
    return centre - Decimal('0.99') <= vat <= centre + Decimal('0.99')


def _special(names, rows, period_code, own_tin):
    errors = []

    seen = set()
    for row in rows:
        s = row['serial no']
        if s in seen:
            if not any(e['serial'] == s for e in errors):
                errors.append({'serial': s, 'message': 'Serial No provided is duplicate'})
                if len(errors) + 1 >= MAX_ERRORS:
                    return TOO_MANY, errors
        else:
            seen.add(s)

    if len(names) != len(COLUMNS):
        return 'Validation failed', errors + [{'serial': 'NA', 'message': 'Invalid Column Count'}]

    invoices = set()
    for row in rows:
        serial = row['serial no']

        def add(msg):
            errors.append({'serial': serial, 'message': msg})

        n = _int32(serial)
        if n is None:
            raise _Fail('Input string was not in a correct format.')
        if n <= 0:
            add('Serial number is invalid.')

        inv = row['tax invoice no']
        key = inv.upper().strip() + row["supplier's tin"].upper().strip()
        if key in invoices:
            add('Duplicated Tax Invoice from same supplier.')
        else:
            invoices.add(key)
        if ' ' in inv:
            add('Tax Invoice No entered is invalid. Please remove spaces.')
        if not re.fullmatch(r'[a-zA-Z0-9_/-]{0,40}', inv):
            add('The invoice number contains invalid character(s).')

        when = _parse_mdy(row['invoice date'].strip())
        if period_code:
            period = period_code_dates(period_code)
            if period is None:
                raise _Fail('String reference not set to an instance of a String.\r\nParameter name: s')
            if when > period[1]:
                add('Invoice date should not be after the end of the taxable period.')

        value = _decimal(row['value of purchase'])
        vat = _decimal(row['vat amount'])
        rate, b1, b2, rate2 = _rates(when)
        if value < 0:
            add('Value of purchase can not be a negative value')
        elif not _within(vat, value, rate):
            if not (_within(vat, value, b1) or _within(vat, value, b2) or _within(vat, value, rate2)):
                add('VAT amount should be equal to (value of purchase) * Vat rate, applicable to invoice date.')

        disallowed = _decimal(row['disallowed vat amount'])
        if disallowed > vat:
            add('Disallowed tax amount should not exceed vat amount')
        if disallowed < 0:
            add('Disallowed tax amount can not be a negative value.')

        tin = row["supplier's tin"]
        if not tin_is_valid(tin):
            add('TIN is not valid.')
        if tin.strip() == own_tin:
            add('Same TIN (indicated in schedule name) cannot be included as part of schedule record')

        if len(errors) >= MAX_ERRORS:
            return TOO_MANY, errors

    return ('Validation Failed' if errors else None), errors


def verify(file_name, content, period_code):
    result = {'passed': False, 'stage': '', 'popup': '', 'errors': []}
    try:
        problem = _check_file_name(file_name)
        if problem:
            result.update(stage='filename', popup=problem)
            return result
        names, rows = _read_table(content)
        if _int32(period_code or '') is None:
            raise _Fail('Input string was not in a correct format.')
        header, errors = _basic(names, rows)
        if header:
            result.update(stage='basic', popup=header, errors=errors)
            return result
        header, errors = _special(names, rows, period_code, file_name.split('_')[0])
        if header:
            result.update(stage='special', popup=header, errors=errors)
            return result
        result.update(passed=True, stage='done', popup='Validation passed!')
    except _Fail as e:
        result['stage'] = 'exception'
        result['popup'] = COMMAS_POPUP if str(e) == '__DUPLICATE__' else 'Error : ' + str(e)
    return result
