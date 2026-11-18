// Front-end tests: npm test
// The 40 reference cases carry the real IRD tool's answers (stage, popup, first error).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const V = require('../verifier.js');

const root = path.join(__dirname, '..');
const { cases } = JSON.parse(fs.readFileSync(path.join(__dirname, 'cases.json'), 'utf8'));

for (const c of cases) {
  test('case ' + c.name, () => {
    const r = V.verify(c.file, new Uint8Array(Buffer.from(c.b64, 'base64')), c.period);
    assert.strictEqual(r.stage, c.expect.stage);
    assert.strictEqual(r.popup, c.expect.popup);
    assert.strictEqual(r.passed, c.expect.stage === 'done');
    if (c.expect.first) assert.deepStrictEqual([r.errors[0].serial, r.errors[0].message], c.expect.first);
  });
}

test('period codes', () => {
  assert.strictEqual(V.periodCodeFor(2026, [10, 11, 12]), '2640');
  assert.strictEqual(V.periodCodeFor(2026, [11]), '2642');
  assert.strictEqual(V.periodCodeFor(2026, [1]), '2611');
  assert.strictEqual(V.periodCodeFor(2026, [9, 10, 11]), null);
  assert.deepStrictEqual(V.periodCodeDates('2640'), [20261001, 20261231]);
  assert.deepStrictEqual(V.periodCodeDates('2412'), [20240201, 20240229]);
  assert.strictEqual(V.periodCodeDates('2603'), null);
});

test('TIN check digit', () => {
  assert.strictEqual(V.tinIsValid('100000016'), true);
  assert.strictEqual(V.tinIsValid('100000017'), false);
  assert.strictEqual(V.tinIsValid('149000005'), true);
  assert.strictEqual(V.tinIsValid('10000001'), false);
});

test('file name', () => {
  assert.strictEqual(V.fileNameFor('100000016', '2640', new Date(2026, 10, 19)),
    '100000016_VAT_SCHEDULE02_2640_20261119_ORIGINAL_V1.csv');
});

test('index.html carries the current verifier.js', () => {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const lib = fs.readFileSync(path.join(root, 'verifier.js'), 'utf8').trim();
  assert.ok(html.includes(lib), 'index.html is stale: run node tools/build.js');
});
