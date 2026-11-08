#!/usr/bin/env python3
"""Offline submission consistency check against organizer's published tree.
Pinned template tree: 51e25074c9e39fb54b717bc06876afeb2b1a1e09.
No network, no secrets, no modification of user originals.
"""
import csv,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE_FILES=[
 '.gitignore','README.md','config/example.env','docs/ARCHITECTURE.md',
 'docs/LIMITATIONS.md','docs/PROTOCOL.md','docs/TEST_RESULTS.md',
 'src/README.md','artifacts/demo/README.md',
 'artifacts/test-results/README.md','artifacts/test-results/results.csv',
]
TEMPLATE_HEADINGS={
 'docs/ARCHITECTURE.md':['Контекст','Компоненты','Основные технические решения','Зависимости','Безопасность и приватность'],
 'docs/LIMITATIONS.md':['Поддерживаемые условия','Известные ограничения','Что не входит в текущую версию','Риски демонстрации','Дальнейшее развитие'],
 'docs/PROTOCOL.md':['Цели','Физический уровень','Формат передачи','Установление и завершение передачи','Синхронизация','Ошибки и восстановление','Совместимость','Пример'],
}
errors=[]
for name in TEMPLATE_FILES:
 if not (ROOT/name).is_file():errors.append('missing: '+name)
for name,headings in TEMPLATE_HEADINGS.items():
 p=ROOT/name
 if p.exists():
  found=[m.group(1).strip() for m in re.finditer(r'^##\s+(.+)$',p.read_text('utf8'),re.M)]
  for h in headings:
   if h not in found:errors.append(f'missing heading {name}: {h}')
for p in [ROOT/'README.md',*(ROOT/'docs').glob('*.md'),
          ROOT/'src/README.md',ROOT/'src/mobile/README.md',
          ROOT/'artifacts/demo/README.md',ROOT/'artifacts/test-results/README.md']:
 if not p.is_file():continue
 for match in re.finditer(r'(?<!!)\[[^\]]+\]\(([^)]+)\)',p.read_text('utf8',errors='replace')):
  dest=match.group(1).split('#',1)[0]
  if not dest or re.match(r'^[a-zA-Z][\w+.-]*:',dest):continue
  if not (p.parent/dest).exists():errors.append(f'broken link: {p.relative_to(ROOT)} -> {dest}')
jsonpath=ROOT/'artifacts/demo/ITAM-demo-3-speakers-33s-export.json'
if jsonpath.exists():
 try:
  example=json.loads(jsonpath.read_text('utf8'))
  assert set(example)=={'transcript'}
  assert len(example['transcript'])>0
  for row in example['transcript']:
   assert set(row)=={'speaker_id','start_ms','end_ms','text'}
   assert isinstance(row['speaker_id'],str)
   assert type(row['start_ms']) is int and type(row['end_ms']) is int
   assert 0<=row['start_ms']<row['end_ms']
   assert isinstance(row['text'],str)
 except Exception as e:errors.append('invalid demo JSON: '+str(e))
else:errors.append('missing validated demo JSON')
with (ROOT/'artifacts/test-results/results.csv').open(encoding='utf-8-sig',newline='') as f:
 rows=list(csv.DictReader(f))
 if len(rows)<1:errors.append('empty test results CSV')
config=(ROOT/'config/example.env').read_text('utf8')
if re.search(r'(?:TOKEN|PASSWORD|SECRET|API_KEY)\s*=\s*\S+',config,re.I):
 errors.append('suspicious secret-like assignment in example.env')
print('TEMPLATE_SOURCE: https://github.com/grigorevmp/hacathon_template')
print('TEMPLATE_TREE: 51e25074c9e39fb54b717bc06876afeb2b1a1e09')
print('REQUIRED_PATHS: ',len(TEMPLATE_FILES))
print('REQUIRED_SECTION_HEADINGS: ',sum(map(len,TEMPLATE_HEADINGS.values())))
print('DEMO_JSON_REPLIES: ',len(example.get('transcript',[])) if 'example' in locals() else '?')
print('CSV_ROWS: ',len(rows))
print('ERRORS: ',len(errors),errors[:35])
raise SystemExit(bool(errors))
