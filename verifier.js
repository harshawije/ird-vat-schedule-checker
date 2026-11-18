/*
 * JavaScript port of the Python port of IRD's "Schedule File Verifier" v5.20,
 * VAT Schedule 02 (file type 22032). Same order, rules, messages and quirks.
 * Money is held as BigInt cents so there is no floating-point rounding.
 *
 * IRDVerifier.verify(fileName, bytes:Uint8Array, periodCode) ->
 *   { passed, stage: 'filename'|'basic'|'special'|'exception'|'done', popup, errors:[{serial, message}] }
 */
(function (root) {
  'use strict';

  var MAX_ERRORS = 100;
  var COLUMNS = [
    ['Serial No', 'int', 10],
    ['Invoice Date', 'str', null],
    ['Tax Invoice No', 'str', 40],
    ["Supplier's TIN", 'str', 9],
    ['Name of the Supplier', 'str', 100],
    ['Description', 'str', 500],
    ['Value of purchase', 'dec', 15],
    ['VAT Amount', 'dec', 15],
    ['Disallowed VAT Amount', 'dec', 15]
  ];
  var CODE_HEADER = {
    F001: 'File schema mismatch.',
    F002: 'Mandatory data not available.',
    F003: 'Data type mismatch.',
    F004: 'Data type mismatch.',
    F005: 'Maximum length of records exceeded.',
    S616: 'The Schedule file is rejected due to unavailability of records.'
  };
  var NO_RECORDS = 'The Schedule file is rejected due to unavailability of records.';
  var COMMAS_POPUP = "Please make sure there are no 'commas' in the data and try again.";
  var TOO_MANY = '\r\nToo many errors to show. Maximum is 100';

  // Dates as yyyymmdd numbers, so plain < and > compare them.
  function ymd(y, m, d) { return y * 10000 + m * 100 + d; }
  var V = {
    d1: ymd(2016, 5, 1), d2: ymd(2016, 7, 12), d3: ymd(2016, 11, 1), d4: ymd(2018, 11, 1),
    d5: ymd(2019, 6, 1), d6: ymd(2019, 12, 29), d7: ymd(2019, 12, 1), d7e: ymd(2022, 6, 28),
    d8: ymd(2022, 6, 1), d8e: ymd(2022, 9, 28), d9: ymd(2022, 9, 1), d9e: ymd(2024, 1, 28),
    d10: ymd(2024, 1, 1)
  };
  // Rates in hundredths (0.18 -> 18n).
  var R1 = 11n, R2 = 15n, R3 = 5n, R4 = 7n, R5 = 8n, R6 = 12n, R7 = 15n, R8 = 18n;

  function Fail(message) { this.message = message; }

  // Length in code points (Python len()).
  function plen(s) { return Array.from(s).length; }
  function pstrip(s) { return s.replace(/^\s+|\s+$/g, ''); }

  // ------------------------------------------------------------ .NET-alikes

  var INT_RE = /^\s*[+-]?\d+\s*$/;
  var DEC_RE = /^\s*[+-]?(\d[\d,]*)?(\.\d*)?[+-]?\s*$/;

  // Int32.Parse(NumberStyles.Integer); null when it would throw.
  function int32(text) {
    if (!INT_RE.test(text)) return null;
    var v = BigInt(pstrip(text));
    return (v >= -(2n ** 31n) && v < 2n ** 31n) ? Number(v) : null;
  }

  // TypeDescriptor Int32Converter: also takes 0x / &h / # hex.
  function int32ConverterOk(text) {
    var t = pstrip(text);
    var prefixes = ['0x', '0X', '&h', '&H', '#'];
    for (var i = 0; i < prefixes.length; i++) {
      if (t.indexOf(prefixes[i]) === 0) {
        // Python int(x, 16): optional sign, optional 0x, underscores between digits.
        var m = /^\s*([+-]?)(?:0[xX])?([0-9a-fA-F]+(?:_[0-9a-fA-F]+)*)\s*$/.exec(t.slice(prefixes[i].length));
        if (!m) return false;
        var v = BigInt('0x' + m[2].replace(/_/g, ''));
        if (m[1] === '-') v = -v;
        return v < 2n ** 32n;
      }
    }
    return int32(text) !== null;
  }

  // Decimal.Parse(NumberStyles.Number) -> {m: BigInt mantissa, s: scale} or null.
  function decimal(text) {
    if (!DEC_RE.test(text) || !/\d/.test(text)) return null;
    var t = pstrip(text);
    var neg = false;
    if (t[0] === '+' || t[0] === '-') {
      neg = t[0] === '-';
      t = t.slice(1);
    } else if (t.slice(-1) === '+' || t.slice(-1) === '-') {
      neg = t.slice(-1) === '-';
      t = t.slice(0, -1);
    }
    t = t.replace(/,/g, '');
    if (t[0] === '.') t = '0' + t;
    if (t.slice(-1) === '.') t = t.slice(0, -1);
    if (!/^\d+(\.\d+)?$/.test(t)) return null;   // Decimal() would throw
    var parts = t.split('.');
    var frac = parts[1] || '';
    var m = BigInt(parts[0] + frac);
    return { m: neg ? -m : m, s: frac.length };
  }

  // Exactly representable in cents? (round2(x) == x)
  function hasAtMost2dp(d) {
    if (d.s <= 2) return true;
    return d.m % (10n ** BigInt(d.s - 2)) === 0n;
  }
  // Value in cents; only call when hasAtMost2dp.
  function cents(d) {
    return d.s <= 2 ? d.m * 10n ** BigInt(2 - d.s) : d.m / 10n ** BigInt(d.s - 2);
  }

  var FLOAT_RE = /^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\s*$/;
  var DEC_LIMIT = 79228162514264337593543950336n;

  // DecimalConverter = Decimal.Parse(NumberStyles.Float): sign and exponent
  // allowed, trailing sign and thousands separators not.
  function decimalConverterOk(text) {
    var m = FLOAT_RE.exec(text);
    if (!m) return false;
    var mant = m[1];
    var exp = m[2] ? parseInt(m[2].slice(1), 10) : 0;
    var dot = mant.indexOf('.');
    var digits = mant.replace('.', '');
    var fracLen = dot < 0 ? 0 : mant.length - dot - 1;
    var mm = BigInt(digits);
    if (mm === 0n) return true;
    var k = exp - fracLen;
    if (k > 400) return false;
    if (k < -400 - digits.length) return true;
    return k >= 0 ? mm * 10n ** BigInt(k) < DEC_LIMIT : mm < DEC_LIMIT * 10n ** BigInt(-k);
  }

  var DATE_RE = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/;

  function daysIn(y, m) { return new Date(Date.UTC(y, m, 0)).getUTCDate(); }

  // DateTime.ParseExact(text, "M/d/yyyy"); null when it throws.
  function parseMdy(text) {
    var m = DATE_RE.exec(text);
    if (!m) return null;
    var mo = +m[1], d = +m[2], y = +m[3];
    if (y < 1 || mo < 1 || mo > 12 || d < 1) return null;
    var dim = [31, (y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0)) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1];
    if (d > dim) return null;
    return ymd(y, mo, d);
  }

  // TPRHelper.ValidateTIN: 9 digits with IRD's check digit (or 149000001-149002622).
  function tinIsValid(tin) {
    if (tin.length !== 9 || !/^[0-9]{9}$/.test(tin)) return false;
    var d = tin.split('').map(Number);
    var s = 3 * d[0] + 2 * d[1];
    for (var j = 3; j <= 8; j++) s += d[j - 1] * (10 - j);
    var check = 11 - s % 11;
    if (check === 10 || check === 11) check = 0;
    if (check === d[8]) return true;
    var n = +tin;
    return n >= 149000001 && n <= 149002622;
  }

  // ------------------------------------------------------------ period code

  // [startYmd, endYmd] for a VAT period code, or null if the tool rejects it.
  function periodCodeDates(code) {
    if (!/^[0-9]{2}[1-4][0-3]$/.test(code || '')) return null;
    var year = 2000 + +code.slice(0, 2), q = +code[2], mo = +code[3];
    var first, last;
    if (mo === 0) { first = (q - 1) * 3 + 1; last = first + 2; }
    else { first = last = (q - 1) * 3 + mo; }
    return [ymd(year, first, 1), ymd(year, last, daysIn(year, last))];
  }

  // The code for one calendar month, or a whole calendar quarter; null otherwise.
  function periodCodeFor(year, months) {
    months = months.slice().sort(function (a, b) { return a - b; });
    var q = Math.floor((months[0] - 1) / 3) + 1;
    var yy = String(year % 100).padStart(2, '0');
    if (months.length === 1) return yy + q + ((months[0] - 1) % 3 + 1);
    if (months.length === 3 && months[0] === (q - 1) * 3 + 1 && months[1] === (q - 1) * 3 + 2 && months[2] === (q - 1) * 3 + 3) return yy + q + '0';
    return null;
  }

  function fileNameFor(ownTin, code, madeOn, version) {
    var d = madeOn;
    var stamp = d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0');
    return ownTin + '_VAT_SCHEDULE02_' + code + '_' + stamp + '_ORIGINAL_V' + (version || 1) + '.csv';
  }

  // ------------------------------------------------------------ the steps

  function checkFileName(name) {
    var parts = name.split('_');
    if (parts.length < 4) throw new Fail('Index was outside the bounds of the array.');
    var tinOk = tinIsValid(parts[0]);
    var pattern = pstrip(parts[0]) + '_VAT_SCHEDULE02_' + parts[3] +
      '_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_ORIGINAL_V(\\d+).CSV';
    if (!tinOk) return 'TIN number enter in name is invalid.';
    var matched;
    try { matched = new RegExp(pattern).test(pstrip(name.toUpperCase())); }
    catch (e) { throw new Fail(e.message); }
    if (!matched || plen(parts[3]) !== 4) return 'Name of the file is incorrect.';
    if (parts.length < 5) throw new Fail('Index was outside the bounds of the array.');
    if (plen(parts[4]) !== 8) return 'Name of the file is incorrect.';
    return null;
  }

  function decodeUtf32(bytes, little) {
    var out = '';
    for (var i = 0; i + 3 < bytes.length; i += 4) {
      var cp = little
        ? (bytes[i] | bytes[i + 1] << 8 | bytes[i + 2] << 16 | bytes[i + 3] << 24) >>> 0
        : (bytes[i] << 24 | bytes[i + 1] << 16 | bytes[i + 2] << 8 | bytes[i + 3]) >>> 0;
      out += cp > 0x10FFFF || (cp >= 0xD800 && cp <= 0xDFFF) ? '�' : String.fromCodePoint(cp);
    }
    if (bytes.length % 4) out += '�';
    return out;
  }

  function startsWith(bytes, sig) {
    if (bytes.length < sig.length) return false;
    for (var i = 0; i < sig.length; i++) if (bytes[i] !== sig[i]) return false;
    return true;
  }

  function decode(bytes) {
    if (startsWith(bytes, [0xEF, 0xBB, 0xBF])) return new TextDecoder('utf-8').decode(bytes.subarray(3));
    if (startsWith(bytes, [0xFF, 0xFE, 0, 0])) return decodeUtf32(bytes.subarray(4), true);
    if (startsWith(bytes, [0, 0, 0xFE, 0xFF])) return decodeUtf32(bytes.subarray(4), false);
    if (startsWith(bytes, [0xFF, 0xFE])) return new TextDecoder('utf-16le', { ignoreBOM: true }).decode(bytes.subarray(2));
    if (startsWith(bytes, [0xFE, 0xFF])) return new TextDecoder('utf-16be', { ignoreBOM: true }).decode(bytes.subarray(2));
    return new TextDecoder('utf-8', { ignoreBOM: true }).decode(bytes);
  }

  // FileValidatorUtil.ReadFile -> {names, rows (objects keyed by lower-case name)}.
  function readTable(bytes) {
    var text = decode(bytes);
    var lines = text.split(/\r\n|\r|\n/);
    if (lines.length && lines[lines.length - 1] === '') lines.pop();
    if (!lines.length) throw new Fail('FileEmpty');

    // ',' only if each of the first 10 lines has one and all split the same.
    var sample = lines.slice(0, 10), count = null, i = 0;
    while (i < sample.length && sample[i].indexOf(',') >= 0) {
      var n = sample[i].split(',').length;
      if (count === null) count = n;
      else if (n !== count) break;
      i++;
    }
    var chosen = i === sample.length;
    var split = chosen ? function (s) { return s.split(','); } : function (s) { return s.split(/\s/); };

    var header = split(lines[0]).map(function (h) { return pstrip(h.toLowerCase()); });
    var names = [], seen = new Set(), auto = 1;
    header.forEach(function (h) {
      if (h === '') {
        while (seen.has('column' + auto)) auto++;
        h = 'column' + auto;
      }
      if (seen.has(h)) throw new Fail('__DUPLICATE__');
      seen.add(h);
      names.push(h);
    });

    var rows = [];
    lines.slice(1).forEach(function (line, idx) {
      var fields = split(line);
      if (!fields.some(function (f) { return f !== ''; })) return;
      var row = {};
      names.forEach(function (nm) { row[nm] = ''; });
      fields.slice(0, names.length).forEach(function (f, k) { row[names[k]] = f; });
      Object.defineProperty(row, '_line', { value: idx + 2, enumerable: false });
      rows.push(row);
    });
    return { names: names, rows: rows };
  }

  function basic(names, rows) {
    var errors = [], codes = [];
    var missing = COLUMNS.filter(function (c) { return names.indexOf(c[0].toLowerCase()) < 0; });
    if (missing.length) {
      return ['File schema mismatch.,', missing.map(function (c) {
        return { serial: 'NA', message: "Column '" + c[0] + "' is required based on the file specification." };
      })];
    }
    if (!rows.length) return [CODE_HEADER.S616 + ',', [{ serial: 'NA', message: NO_RECORDS }]];

    var failing = 0;
    for (var r = 0; r < rows.length; r++) {
      var row = rows[r], rowErrors = [];
      COLUMNS.forEach(function (c) {
        var col = c[0], kind = c[1], length = c[2];
        var v = row[col.toLowerCase()], code = null, msg = null;
        if (v === '') { code = 'F002'; msg = 'RequiredFieldMissing'; }
        else if (kind === 'int' && !int32ConverterOk(v)) { code = 'F003'; msg = 'InvalidDataType'; }
        else if (kind === 'dec' && !decimalConverterOk(v)) { code = 'F003'; msg = 'InvalidDataType'; }
        else if (kind === 'dec') {
          var parsed = decimal(v);
          if (plen(v.replace(/\./g, '')) > length || parsed === null || !hasAtMost2dp(parsed)) {
            code = 'F004'; msg = 'Decimal value require ' + length + ' digit and 2 decimal places.';
          }
        } else if (length !== null && plen(v) > length) { code = 'F005'; msg = 'InvalidStringLength'; }
        if (code) rowErrors.push([code, "Column '" + col + "' with data '" + v + "' failed on validation due to " + msg + '.']);
      });
      if (rowErrors.length) {
        failing++;
        rowErrors.forEach(function (e) { if (codes.indexOf(e[0]) < 0) codes.push(e[0]); });
        rowErrors.forEach(function (e) { errors.push({ serial: row['serial no'], message: e[1] }); });
      }
      if (failing >= MAX_ERRORS) break;
    }
    if (errors.length) return [codes.map(function (c) { return CODE_HEADER[c] + ','; }).join(''), errors];

    var dateErrors = rows.filter(function (row) {
      var t = pstrip(row['invoice date']);
      return t && parseMdy(t) === null;
    }).map(function (row) { return { serial: row['serial no'], message: 'Date format is not correct in Invoice Date' }; });
    if (dateErrors.length) return ['Date format is incorrect.', dateErrors];
    return [null, []];
  }

  // GetVATRate: [rate, rateB1, rateB2, rate2]; any within +/-0.99 passes.
  function rates(d) {
    var rate = 0n, b1 = 0n, b2 = 0n, rate2 = 0n;
    if (d <= V.d1) rate = R1;
    else if (V.d1 < d && d < V.d2) rate = R2;
    else if (V.d2 <= d && d < V.d3) rate = R1;
    else if (V.d3 <= d && d < V.d4) rate = R2;
    else if (V.d4 <= d && d < V.d5) { rate = R2; rate2 = R3; }
    else if (V.d5 <= d && d < V.d7) { rate = R2; rate2 = R3; b1 = R4; }
    else if (V.d7 <= d && d < V.d6) { rate = R2; rate2 = R3; b1 = R4; b2 = R5; }
    else if (V.d6 <= d && d < V.d8) rate = R5;
    else if (V.d8 <= d && d <= V.d7e) { rate = R5; rate2 = R6; }
    else if (V.d8 <= d && d < V.d9) rate = R6;
    else if (V.d9 <= d && d <= V.d8e) { rate = R6; rate2 = R7; }
    else if (V.d9 <= d && d < V.d10) rate = R7;
    else if (V.d10 <= d && d <= V.d9e) { rate = R7; rate2 = R8; }
    else if (d >= V.d10) rate = R8;
    return [rate, b1, b2, rate2];
  }

  // round(rate x value, 2) half away from zero, in cents.
  function centreCents(valueCents, rate) {
    var p = valueCents * rate;               // units of 0.0001
    var a = p < 0n ? -p : p;
    var q = (a + 50n) / 100n;
    return p < 0n ? -q : q;
  }
  function within(vat, value, rate) {
    var c = centreCents(value, rate);
    return c - 99n <= vat && vat <= c + 99n;
  }

  function special(names, rows, periodCode, ownTin) {
    var errors = [];
    var seen = new Set();
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i]['serial no'];
      if (seen.has(s)) {
        if (!errors.some(function (e) { return e.serial === s; })) {
          errors.push({ serial: s, message: 'Serial No provided is duplicate' });
          if (errors.length + 1 >= MAX_ERRORS) return [TOO_MANY, errors];
        }
      } else seen.add(s);
    }

    if (names.length !== COLUMNS.length) {
      return ['Validation failed', errors.concat([{ serial: 'NA', message: 'Invalid Column Count' }])];
    }

    var invoices = new Set();
    for (var r = 0; r < rows.length; r++) {
      var row = rows[r], serial = row['serial no'];
      var add = function (msg) { errors.push({ serial: serial, message: msg }); };

      var n = int32(serial);
      if (n === null) throw new Fail('Input string was not in a correct format.');
      if (n <= 0) add('Serial number is invalid.');

      var inv = row['tax invoice no'];
      var key = pstrip(inv.toUpperCase()) + pstrip(row["supplier's tin"].toUpperCase());
      if (invoices.has(key)) add('Duplicated Tax Invoice from same supplier.');
      else invoices.add(key);
      if (inv.indexOf(' ') >= 0) add('Tax Invoice No entered is invalid. Please remove spaces.');
      if (!/^[a-zA-Z0-9_/-]{0,40}$/.test(inv)) add('The invoice number contains invalid character(s).');

      var when = parseMdy(pstrip(row['invoice date']));
      if (when === null) throw new Fail('Invoice Date could not be read.');  // the Python port crashes here
      if (periodCode) {
        var period = periodCodeDates(periodCode);
        if (period === null) throw new Fail('String reference not set to an instance of a String.\r\nParameter name: s');
        if (when > period[1]) add('Invoice date should not be after the end of the taxable period.');
      }

      var value = cents(decimal(row['value of purchase']));
      var vat = cents(decimal(row['vat amount']));
      var rt = rates(when);
      if (value < 0n) add('Value of purchase can not be a negative value');
      else if (!within(vat, value, rt[0])) {
        if (!(within(vat, value, rt[1]) || within(vat, value, rt[2]) || within(vat, value, rt[3]))) {
          add('VAT amount should be equal to (value of purchase) * Vat rate, applicable to invoice date.');
        }
      }

      var disallowed = cents(decimal(row['disallowed vat amount']));
      if (disallowed > vat) add('Disallowed tax amount should not exceed vat amount');
      if (disallowed < 0n) add('Disallowed tax amount can not be a negative value.');

      var tin = row["supplier's tin"];
      if (!tinIsValid(tin)) add('TIN is not valid.');
      if (pstrip(tin) === ownTin) add('Same TIN (indicated in schedule name) cannot be included as part of schedule record');

      if (errors.length >= MAX_ERRORS) return [TOO_MANY, errors];
    }
    return [errors.length ? 'Validation Failed' : null, errors];
  }

  // Run the whole check exactly as the Verify button does. Also returns the
  // parsed rows (when it got that far) so a page can show supplier names.
  function verify(fileName, bytes, periodCode) {
    var result = { passed: false, stage: '', popup: '', errors: [], rows: null };
    try {
      var problem = checkFileName(fileName);
      if (problem) { result.stage = 'filename'; result.popup = problem; return result; }
      var t = readTable(bytes);
      result.rows = t.rows;
      if (int32(periodCode || '') === null) throw new Fail('Input string was not in a correct format.');
      var b = basic(t.names, t.rows);
      if (b[0]) { result.stage = 'basic'; result.popup = b[0]; result.errors = b[1]; return result; }
      var sp = special(t.names, t.rows, periodCode, fileName.split('_')[0]);
      if (sp[0]) { result.stage = 'special'; result.popup = sp[0]; result.errors = sp[1]; return result; }
      result.passed = true; result.stage = 'done'; result.popup = 'Validation passed!';
    } catch (e) {
      if (!(e instanceof Fail)) throw e;
      result.stage = 'exception';
      result.popup = e.message === '__DUPLICATE__' ? COMMAS_POPUP : 'Error : ' + e.message;
    }
    return result;
  }

  var api = {
    verify: verify, tinIsValid: tinIsValid, periodCodeDates: periodCodeDates,
    periodCodeFor: periodCodeFor, fileNameFor: fileNameFor, COLUMNS: COLUMNS
  };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.IRDVerifier = api;
})(this);
