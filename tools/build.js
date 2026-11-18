// Builds index.html from tools/page.html, inlining verifier.js so the page is
// one self-contained file that also works offline.  Run: node tools/build.js
const fs = require('fs');
const path = require('path');
const root = path.join(__dirname, '..');
const page = fs.readFileSync(path.join(__dirname, 'page.html'), 'utf8');
const lib = fs.readFileSync(path.join(root, 'verifier.js'), 'utf8');
const body = page.replace('/*VERIFIER*/', () => lib.trim());
const head = body.slice(0, body.indexOf('<div class="wrap">'));
const rest = body.slice(body.indexOf('<div class="wrap">'));
const html = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n' +
  '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' +
  head.trim() + '\n</head>\n<body>\n' + rest.trim() + '\n</body>\n</html>\n';
fs.writeFileSync(path.join(root, 'index.html'), html);
console.log('index.html written (' + html.length + ' bytes)');
