"""python3 -m unittest discover -s tests   (checks the Python port against the same 40 cases)"""
import base64
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'python'))
import ird_schedule_verifier as v  # noqa: E402


class ReferenceCases(unittest.TestCase):
    def test_cases(self):
        for c in json.load(open(os.path.join(HERE, 'cases.json')))['cases']:
            with self.subTest(c['name']):
                r = v.verify(c['file'], base64.b64decode(c['b64']), c['period'])
                self.assertEqual(r['stage'], c['expect']['stage'])
                self.assertEqual(r['popup'], c['expect']['popup'])
                if c['expect']['first']:
                    self.assertEqual([r['errors'][0]['serial'], r['errors'][0]['message']], c['expect']['first'])

    def test_period_and_tin(self):
        self.assertEqual(v.period_code_for(2026, [10, 11, 12]), '2640')
        self.assertIsNone(v.period_code_dates('2603'))
        self.assertTrue(v.tin_is_valid('100000016'))
        self.assertFalse(v.tin_is_valid('100000017'))


if __name__ == '__main__':
    unittest.main()
