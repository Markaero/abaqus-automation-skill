#!/usr/bin/env python3
"""Consistency checks for this kit. Run with plain Python 3 (no Abaqus):

    python3 tools/check_consistency.py

Catches the drift that bit earlier versions: the kit contradicting its
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


def script_files():
    out = []
    for d, _, files in os.walk(os.path.join(ROOT, 'scripts')):
        for n in files:
            if n.endswith('.py'):
                out.append(os.path.relpath(os.path.join(d, n), ROOT))
    return sorted(out)


# 1. Scripts (incl. abqlib) compile and use a utf-8 header (gotcha #35)
for rel in script_files():
    try:
        py_compile.compile(os.path.join(ROOT, rel), doraise=True)
    except py_compile.PyCompileError as exc:
        errors.append('%s: does not compile: %s' % (rel, exc))
    if not read(rel).startswith('# -*- coding: utf-8 -*-'):
        errors.append('%s: first line must be "# -*- coding: utf-8 -*-"' % rel)

# 2. Code (scripts + python snippets) must follow the kit's own gotchas
code_sources = [(rel, read(rel)) for rel in script_files()]
md_files = ['AGENTS.md', 'SKILL.md'] + [os.path.join('references', n)
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

# 4. abqlib stays Py 2.7 compatible (Abaqus <=2023)
for rel in script_files():
    code = read(rel)
    if re.search(r'''(?<![\w'"])f['"]''', code):
        errors.append('%s: f-string (breaks Abaqus Py 2.7)' % rel)
    if re.search(r'\bnonlocal\b|yield from|^\s*async\s+def|:=', code, re.M):
        errors.append('%s: Py3-only syntax (breaks Abaqus Py 2.7)' % rel)

# 5. API catalog regenerated from the current docstrings
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import gen_catalog  # noqa: E402
if read(os.path.join('references', 'api_catalog.md')) != gen_catalog.build():
    errors.append('references/api_catalog.md is stale: run python3 tools/gen_catalog.py')

# 6. SKILL.md is a frontmatter shim pointing at AGENTS.md
skill = read('SKILL.md')
if not re.match(r'---\nname: [a-z0-9-]+\ndescription: .+?\n---\n', skill, re.S):
    errors.append('SKILL.md: missing/invalid name+description frontmatter')
if 'AGENTS.md' not in skill or len(skill.split('\n---\n', 1)[-1].splitlines()) > 15:
    errors.append('SKILL.md: body must stay a short pointer to AGENTS.md')

# 7. AGENTS.md usage part stays agent-neutral (no vendor tool names/paths)
usage = read('AGENTS.md').split('## Maintaining This Kit')[0]
for pat in (r'\.claude/', r'~/\.codex', r'\bSkill tool\b', r'AskUserQuestion', r'\bTodoWrite\b',
            r'mcp__', r'claude\.ai'):
    if re.search(pat, usage):
        errors.append('AGENTS.md: vendor-specific reference %r in the usage part' % pat)

if errors:
    print('FAIL (%d)' % len(errors))
    for e in errors:
        print('  - ' + e)
    sys.exit(1)
print('OK: %d scripts, %d markdown files checked, %d gotchas'
      % (len([s for s in code_sources if s[0].endswith('.py')]), len(md_files), len(nums)))
