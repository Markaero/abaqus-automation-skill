#!/usr/bin/env python3
"""Consistency checks for this skill. Run with plain Python 3 (no Abaqus):

    python3 tools/check_skill.py

Catches the drift that bit earlier versions: the skill contradicting its
own gotchas in scripts and code snippets.
"""

import os
import py_compile
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []


def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def md_python_blocks(text):
    return re.findall(r'```python\n(.*?)```', text, re.S)


# 1. Scripts compile and use a utf-8 header (gotcha #35)
for name in sorted(os.listdir(os.path.join(ROOT, 'scripts'))):
    if not name.endswith('.py'):
        continue
    rel = os.path.join('scripts', name)
    try:
        py_compile.compile(os.path.join(ROOT, rel), doraise=True)
    except py_compile.PyCompileError as exc:
        errors.append('%s: does not compile: %s' % (rel, exc))
    if not read(rel).startswith('# -*- coding: utf-8 -*-'):
        errors.append('%s: first line must be "# -*- coding: utf-8 -*-"' % rel)

# 2. Code (scripts + python snippets) must follow the skill's own gotchas
code_sources = [(os.path.join('scripts', n), read(os.path.join('scripts', n)))
                for n in os.listdir(os.path.join(ROOT, 'scripts')) if n.endswith('.py')]
md_files = ['SKILL.md'] + [os.path.join('references', n)
                           for n in sorted(os.listdir(os.path.join(ROOT, 'references')))
                           if n.endswith('.md')]
for rel in md_files:
    for block in md_python_blocks(read(rel)):
        code_sources.append((rel, block))

for rel, code in code_sources:
    if re.search(r'coding:\s*mbcs', code):
        errors.append('%s: uses mbcs coding header (gotcha #35)' % rel)
    for m in re.finditer(r'\bsum\((?!\[)[^\n]*\bfor\b', code):
        errors.append('%s: sum() over a generator (gotcha #16): %s' % (rel, m.group(0)))
    if re.search(r'__file__', code) and 'noGUI' not in code:
        errors.append('%s: uses __file__ (undefined under noGUI, gotcha #32)' % rel)

# 3. Gotcha table numbered 1..N in order
api = read(os.path.join('references', 'abaqus_api.md'))
nums = [int(n) for n in re.findall(r'^\| (\d+) \| \*\*', api, re.M)]
if nums != list(range(1, len(nums) + 1)):
    errors.append('references/abaqus_api.md: gotcha rows not numbered 1..N in order: %s' % nums)

# 4. SKILL.md frontmatter
skill = read('SKILL.md')
if not re.match(r'---\nname: [a-z0-9-]+\ndescription: .+?\n---\n', skill, re.S):
    errors.append('SKILL.md: missing/invalid name+description frontmatter')

if errors:
    print('FAIL (%d)' % len(errors))
    for e in errors:
        print('  - ' + e)
    sys.exit(1)
print('OK: %d scripts, %d markdown files checked, %d gotchas'
      % (len([s for s in code_sources if s[0].endswith('.py')]), len(md_files), len(nums)))
