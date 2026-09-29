#!/usr/bin/env python3
"""Look up the Abaqus scripting API offline, from abqpy's documented stubs.

abqpy (https://github.com/haiiliin/abqpy, MIT) mirrors the official Abaqus
Scripting Reference as Python stubs with full docstrings, one release per
Abaqus version. Read it before using any Abaqus call that abqlib does not
wrap - most "gotchas" are simply documented behavior.

One-time setup (plain Python 3.9+, no Abaqus needed; match your version):

    pip install --no-deps --target .abqpy "abqpy==2024.*"

Usage:

    python3 tools/api_lookup.py ConcentratedForce      # class: members + docs
    python3 tools/api_lookup.py DatumCsysByThreePoints # method: signature + docs
    python3 tools/api_lookup.py --search Csys          # list matching names

Stub location, first found: --stubs DIR, $ABQPY_STUBS, <kit>/.abqpy,
an installed abqpy distribution.
"""

import argparse
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_stub_root(explicit=None):
    """Directory that contains abqpy's 'abaqus' stub package, or None."""
    candidates = [explicit, os.environ.get('ABQPY_STUBS'), os.path.join(ROOT, '.abqpy')]
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, 'abaqus')):
            return c
    try:
        from importlib import metadata
        dist = metadata.distribution('abqpy')
        path = str(dist.locate_file(''))
        if os.path.isdir(os.path.join(path, 'abaqus')):
            return path
    except Exception:
        pass
    return None


def stub_files(root):
    """All stub files; model-database (mdb) definitions before ODB ones."""
    paths = []
    for d, _, files in os.walk(os.path.join(root, 'abaqus')):
        for n in files:
            if n.endswith('.py'):
                paths.append(os.path.join(d, n))
    return sorted(paths, key=lambda p: ('Odb' in os.path.relpath(p, root), p))


def _member_docs(src_lines, cls):
    """[(name, annotation, doc)] for annotated class attributes and their '#:' comments."""
    out = []
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            doc = []
            i = node.lineno - 2
            while i >= 0 and src_lines[i].strip().startswith('#:'):
                doc.insert(0, src_lines[i].strip()[2:].strip())
                i -= 1
            out.append((node.target.id, ast.unparse(node.annotation), ' '.join(doc)))
    return out


def lookup(root, name, max_doc=60):
    hits = 0
    for path in stub_files(root):
        with open(path, encoding='utf-8') as f:
            src = f.read()
        if name not in src:
            continue
        tree = ast.parse(src)
        lines = src.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
                hits += 1
                rel = os.path.relpath(path, root)
                print('=' * 78)
                if isinstance(node, ast.ClassDef):
                    print('class %s   [%s]' % (name, rel))
                    members = _member_docs(lines, node)
                    if members:
                        print('\nMembers (attributes you can read):')
                        for m, ann, doc in members:
                            print('  %-28s %s' % (m, doc or ann))
                    methods = [b.name for b in node.body
                               if isinstance(b, ast.FunctionDef) and not b.name.startswith('_')]
                    if methods:
                        print('\nMethods: %s' % ', '.join(methods))
                else:
                    print('def %s(%s)   [%s]' % (name, ast.unparse(node.args), rel))
                doc = ast.get_docstring(node) or '(no docstring)'
                doc_lines = doc.splitlines()
                print('\n' + '\n'.join(doc_lines[:max_doc]))
                if len(doc_lines) > max_doc:
                    print('... (%d more lines; open %s)' % (len(doc_lines) - max_doc, rel))
    return hits


def search(root, text):
    text_l = text.lower()
    found = set()
    for path in stub_files(root):
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and text_l in node.name.lower() \
                    and not node.name.startswith('_'):
                found.add((node.name, 'class' if isinstance(node, ast.ClassDef) else 'def'))
    for n, kind in sorted(found):
        print('%-5s %s' % (kind, n))
    return len(found)


def main():
    ap = argparse.ArgumentParser(description='Offline Abaqus API lookup via abqpy stubs.')
    ap.add_argument('name', help='class or method name, e.g. Coupling')
    ap.add_argument('--search', action='store_true', help='list names containing NAME')
    ap.add_argument('--stubs', help='directory containing the abqpy "abaqus" package')
    ap.add_argument('--max-doc', type=int, default=60, help='docstring lines to print')
    args = ap.parse_args()
    root = find_stub_root(args.stubs)
    if root is None:
        print('abqpy stubs not found. Install once (match your Abaqus version):\n'
              '  pip install --no-deps --target %s "abqpy==2024.*"' % os.path.join(ROOT, '.abqpy'))
        sys.exit(2)
    n = search(root, args.name) if args.search else lookup(root, args.name, args.max_doc)
    if n == 0:
        print('No match for %r. Try --search.' % args.name)
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except BrokenPipeError:      # output piped into head/less
        sys.exit(0)
