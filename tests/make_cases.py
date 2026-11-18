"""Builds the 40 reference cases (from the real IRD engine's answers) as JSON.

python3 tests/make_cases.py 100000016 > tests/cases.json
Each case: name, file (file name), b64 (file bytes), period, expect {stage, popup, first}.
"""
import base64
import json
import sys

OWN = sys.argv[1] if len(sys.argv) > 1 else '100000016'
BAD = OWN[:-1] + str((int(OWN[-1]) + 1) % 10)
S1, S2, S3 = '100000024', '100000032', '100000040'
HEADER = ["Serial No", "Invoice Date", "Tax Invoice No", "Supplier's TIN", "Name of the Supplier",
          "Description", "Value of purchase", "VAT Amount", "Disallowed VAT Amount"]


def base_rows():
    return [
        ['1', '10/05/2026', 'INV-1001', S1, 'Supplier One', 'Goods', '5000.00', '900.00', '0.00'],
        ['2', '10/12/2026', 'B-2002', S2, 'Supplier Two', 'Services', '10000.00', '1800.00', '0.00'],
        ['3', '10/20/2026', 'C/3003', S3, 'Supplier Three', 'Repairs', '2500.50', '450.09', '0.00'],
    ]


def name_for(code='2641', tin=OWN, tail='_ORIGINAL_V1.csv'):
    return f'{tin}_VAT_SCHEDULE02_{code}_20261119{tail}'


def csv(header, rows, eol='\r\n', extra_lines=None):
    lines = [','.join(header)] + [','.join(r) for r in rows]
    return (eol.join(lines) + eol).encode('utf-8')


def case(name, expect_stage, expect_popup, first=None, *, rows=None, header=None, body=None,
         period='2641', file=None):
    rows = rows if rows is not None else base_rows()
    header = header or HEADER
    data = body if body is not None else csv(header, rows)
    return dict(name=name, file=file or name_for(), b64=base64.b64encode(data).decode(), period=period,
                expect=dict(stage=expect_stage, popup=expect_popup, first=first))


def mod(i, col, val):
    r = base_rows()
    r[i][col] = val
    return r


cases = []
add = cases.append
BASIC_MAND = 'Mandatory data not available.,'
LEN = 'Maximum length of records exceeded.,'
VF = 'Validation Failed'
COMMAS = "Please make sure there are no 'commas' in the data and try again."
VATMSG = 'VAT amount should be equal to (value of purchase) * Vat rate, applicable to invoice date.'

add(case('blank_disallowed', 'basic', BASIC_MAND,
         ['2', "Column 'Disallowed VAT Amount' with data '' failed on validation due to RequiredFieldMissing."],
         rows=mod(1, 8, '')))
add(case('blank_inv', 'basic', BASIC_MAND,
         ['2', "Column 'Tax Invoice No' with data '' failed on validation due to RequiredFieldMissing."],
         rows=mod(1, 2, '')))
r = base_rows()
lines = [','.join(HEADER), ','.join(r[0]), ''] + [','.join(x) for x in r[1:]]
add(case('blank_line_middle', 'exception', COMMAS, body=('\r\n'.join(lines) + '\r\n').encode()))
add(case('comma_in_name', 'exception', COMMAS, rows=mod(1, 4, 'Supplier, One')))
add(case('date_after_period', 'special', VF,
         ['2', 'Invoice date should not be after the end of the taxable period.'], rows=mod(1, 1, '11/05/2026')))
add(case('date_iso', 'basic', 'Date format is incorrect.', ['2', 'Date format is not correct in Invoice Date'],
         rows=mod(1, 1, '2026-10-05')))
add(case('date_no_pad', 'done', 'Validation passed!', rows=mod(1, 1, '10/5/2026')))
add(case('desc_501', 'basic', LEN,
         ['2', "Column 'Description' with data '" + 'D' * 501 + "' failed on validation due to InvalidStringLength."],
         rows=mod(1, 5, 'D' * 501)))
r = base_rows(); r[1][6] = '5000.00'; r[1][7] = '900.00'; r[1][8] = '900.01'
add(case('disallowed_gt_vat', 'special', VF, ['2', 'Disallowed tax amount should not exceed vat amount'], rows=r))
add(case('extra_column', 'special', 'Validation failed', ['NA', 'Invalid Column Count'],
         header=HEADER + ['Extra'], rows=[x + ['x'] for x in base_rows()]))
add(case('fn_amendment', 'filename', 'Name of the file is incorrect.',
         file=name_for(tail='_AMENDMENT_V1.csv')))
add(case('fn_bad_tin', 'filename', 'TIN number enter in name is invalid.', file=name_for(tin=BAD)))
add(case('fn_name_period_differs', 'done', 'Validation passed!', file=name_for(code='2631')))
add(case('fn_suffix', 'filename', 'Name of the file is incorrect.', file=name_for(tail='_ORIGINAL_V1 (1).csv')))
add(case('header_only', 'basic', 'The Schedule file is rejected due to unavailability of records.,',
         ['NA', 'The Schedule file is rejected due to unavailability of records.'], rows=[]))
add(case('inv_41', 'basic', LEN,
         ['2', "Column 'Tax Invoice No' with data '" + 'A' * 41 + "' failed on validation due to InvalidStringLength."],
         rows=mod(1, 2, 'A' * 41)))
add(case('inv_dot', 'special', VF, ['2', 'The invoice number contains invalid character(s).'], rows=mod(1, 2, 'A.77')))
r = base_rows(); r[1][2] = 'inv-1001'; r[1][3] = S1
add(case('inv_dup_case', 'special', VF, ['2', 'Duplicated Tax Invoice from same supplier.'], rows=r))
add(case('inv_space', 'special', VF, ['2', 'Tax Invoice No entered is invalid. Please remove spaces.'],
         rows=mod(1, 2, 'A 77')))
add(case('missing_column', 'basic', 'File schema mismatch.,',
         ['NA', "Column 'Disallowed VAT Amount' is required based on the file specification."],
         header=HEADER[:8], rows=[x[:8] for x in base_rows()]))
add(case('ok', 'done', 'Validation passed!'))
add(case('ok_bom', 'done', 'Validation passed!', body=b'\xef\xbb\xbf' + csv(HEADER, base_rows())))
add(case('ok_quarter', 'done', 'Validation passed!', period='2640', file=name_for(code='2640')))
add(case('pc_empty', 'exception', 'Error : Input string was not in a correct format.', period=''))
add(case('pc_ends_before_dates', 'special', VF,
         ['1', 'Invoice date should not be after the end of the taxable period.'], period='2631'))
add(case('pc_invalid', 'exception',
         'Error : String reference not set to an instance of a String.\r\nParameter name: s', period='2603'))
h = HEADER[:]; h[0], h[1] = h[1], h[0]
add(case('reordered_columns', 'done', 'Validation passed!', header=h,
         rows=[[x[1], x[0]] + x[2:] for x in base_rows()]))
add(case('serial_dup', 'special', VF, ['1', 'Serial No provided is duplicate'], rows=mod(1, 0, '1')))
add(case('serial_zero', 'special', VF, ['0', 'Serial number is invalid.'], rows=mod(1, 0, '0')))
add(case('tin_bad_check', 'special', VF, ['2', 'TIN is not valid.'], rows=mod(1, 3, S2[:-1] + str((int(S2[-1]) + 1) % 10))))
add(case('tin_own', 'special', VF,
         ['2', 'Same TIN (indicated in schedule name) cannot be included as part of schedule record'],
         rows=mod(1, 3, OWN)))
add(case('tin_vat_reg_style', 'basic', LEN,
         ['2', f"Column 'Supplier's TIN' with data '{S2}-7000' failed on validation due to InvalidStringLength."],
         rows=mod(1, 3, S2 + '-7000')))
add(case('total_row', 'basic', BASIC_MAND,
         ['', "Column 'Serial No' with data '' failed on validation due to RequiredFieldMissing."],
         rows=base_rows() + [['', '', '', '', '', '', '17500.50', '3150.09', '0.00']]))
r = mod(1, 6, '5000.001'); r[1][7] = '900.00'
add(case('value_3dp', 'basic', 'Data type mismatch.,',
         ['2', "Column 'Value of purchase' with data '5000.001' failed on validation due to "
               "Decimal value require 15 digit and 2 decimal places.."], rows=r))
r = base_rows(); r[1][6] = '-5000.00'; r[1][7] = '-900.00'
add(case('value_negative', 'special', VF, ['2', 'Value of purchase can not be a negative value'], rows=r))
r = base_rows(); r[1][6] = '5000'; r[1][7] = '0.00'
add(case('value_zero_vat_zero', 'done', 'Validation passed!', rows=r))
r = base_rows(); r[1][6] = '5000'; r[1][7] = '750'
add(case('vat_15pct', 'special', VF, ['2', VATMSG], rows=r))
r = base_rows(); r[1][6] = '5000'; r[1][7] = '750'; r[1][1] = '01/20/2024'
add(case('vat_15pct_jan2024', 'done', 'Validation passed!', rows=r))
r = base_rows(); r[1][6] = '5000'; r[1][7] = '900.99'
add(case('vat_plus_099', 'done', 'Validation passed!', rows=r))
r = base_rows(); r[1][6] = '5000'; r[1][7] = '901.00'
add(case('vat_plus_100', 'special', VF, ['2', VATMSG], rows=r))

json.dump(dict(own=OWN, cases=cases), sys.stdout, indent=1)
