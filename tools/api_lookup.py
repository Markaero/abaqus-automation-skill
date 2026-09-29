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
    python3 tools/api_lookup.py --search Csys          # names containing text
    python3 tools/api_lookup.py --grep "contact"       # names + summaries containing text
    python3 tools/api_lookup.py --areas                # API areas with sizes
    python3 tools/api_lookup.py --area Interaction     # constructors in one area

Stub location, first found: --stubs DIR, $ABQPY_STUBS, <kit>/.abqpy,
an installed abqpy distribution. The same functions back the MCP server
(mcp_server/server.py).
"""

import argparse
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP_HINT = ('abqpy stubs not found. Install once (match your Abaqus version):\n'
              '  pip install --no-deps --target %s "abqpy==2024.*"' % os.path.join(ROOT, '.abqpy'))

# Areas that only matter for GUI plug-ins or display; hidden from --areas.
GUI_AREAS = ('PlugInRegistration', 'Canvas', 'DisplayOptions', 'PlotOptions', 'OdbDisplay',
             'Animation', 'Annotation', 'DisplayGroup', 'UtilityAndView')


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


def stub_files(root, area=None):
    """Stub files (optionally of one area); model-database definitions before ODB ones."""
    base = os.path.join(root, 'abaqus', area) if area else os.path.join(root, 'abaqus')
    paths = []
    for d, _, files in os.walk(base):
        for n in files:
            if n.endswith('.py'):
                paths.append(os.path.join(d, n))
    return sorted(paths, key=lambda p: ('Odb' in os.path.relpath(p, root), p))


def _parse(path):
    with open(path, encoding='utf-8') as f:
        src = f.read()
    return src, ast.parse(src)


def _summary(node):
    doc = ast.get_docstring(node) or ''
    return ' '.join(doc.strip().split('\n\n')[0].split())


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
    """Full documentation of every class/method called `name`. Returns (text, hits)."""
    out, hits = [], 0
    for path in stub_files(root):
        src, tree = None, None
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
                out.append('=' * 78)
                if isinstance(node, ast.ClassDef):
                    out.append('class %s   [%s]' % (name, rel))
                    members = _member_docs(lines, node)
                    if members:
                        out.append('\nMembers (attributes you can read):')
                        for m, ann, doc in members:
                            out.append('  %-28s %s' % (m, doc or ann))
                    methods = [b.name for b in node.body
                               if isinstance(b, ast.FunctionDef) and not b.name.startswith('_')]
                    if methods:
                        out.append('\nMethods: %s' % ', '.join(methods))
                else:
                    out.append('def %s(%s)   [%s]' % (name, ast.unparse(node.args), rel))
                doc_lines = (ast.get_docstring(node) or '(no docstring)').splitlines()
                out.append('\n' + '\n'.join(doc_lines[:max_doc]))
                if len(doc_lines) > max_doc:
                    out.append('... (%d more lines; open %s)' % (len(doc_lines) - max_doc, rel))
    if not hits:
        out.append('No class or method named %r. Try a search.' % name)
    return '\n'.join(out), hits


def search(root, text, in_docs=False, limit=80):
    """Public classes/methods whose name (or, with in_docs, summary) contains text. Returns (text, count)."""
    text_l = text.lower()
    found = {}
    for path in stub_files(root):
        _, tree = _parse(path)
        area = os.path.relpath(path, os.path.join(root, 'abaqus')).split(os.sep)[0]
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)) or node.name.startswith('_'):
                continue
            summary = _summary(node)
            if text_l in node.name.lower() or (in_docs and text_l in summary.lower()):
                kind = 'class' if isinstance(node, ast.ClassDef) else 'def'
                found.setdefault((node.name, kind), (area, summary))
    rows = sorted(found.items(), key=lambda kv: (text_l not in kv[0][0].lower(), kv[0][0]))
    out = ['%-5s %-34s [%s] %s' % (kind, n, area, s[:90]) for (n, kind), (area, s) in rows[:limit]]
    if len(rows) > limit:
        out.append('... %d more; narrow the query' % (len(rows) - limit))
    if not rows:
        out.append('No match for %r.' % text)
    return '\n'.join(out), len(rows)


def areas(root):
    """API areas (stub packages) with their number of constructors. Returns (text, count)."""
    base = os.path.join(root, 'abaqus')
    rows = []
    for area in sorted(os.listdir(base)):
        if area in GUI_AREAS or not os.path.isdir(os.path.join(base, area)):
            continue
        n = len(_constructors(root, area))
        if n:
            rows.append('%-22s %4d constructors' % (area, n))
    return '\n'.join(rows), len(rows)


def _constructors(root, area):
    """{name: summary} of object-creating methods (Capitalized defs) in an area."""
    out = {}
    for path in stub_files(root, area):
        _, tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name[:1].isupper():
                out.setdefault(node.name, _summary(node))
    return out


def list_area(root, area):
    """Constructors of one area with one-line summaries. Returns (text, count)."""
    if not os.path.isdir(os.path.join(root, 'abaqus', area)):
        known = sorted(d for d in os.listdir(os.path.join(root, 'abaqus'))
                       if os.path.isdir(os.path.join(root, 'abaqus', d)))
        return 'Unknown area %r. Areas: %s' % (area, ', '.join(known)), 0
    ctors = _constructors(root, area)
    rows = ['%-36s %s' % (n, s[:100]) for n, s in sorted(ctors.items())]
    return '\n'.join(rows), len(rows)


def main():
    ap = argparse.ArgumentParser(description='Offline Abaqus API lookup via abqpy stubs.')
    ap.add_argument('name', nargs='?', help='class or method name, e.g. Coupling')
    ap.add_argument('--search', metavar='TEXT', help='list names containing TEXT')
    ap.add_argument('--grep', metavar='TEXT', help='list names or summaries containing TEXT')
    ap.add_argument('--areas', action='store_true', help='list API areas')
    ap.add_argument('--area', metavar='AREA', help='list constructors of one area')
    ap.add_argument('--stubs', help='directory containing the abqpy "abaqus" package')
    ap.add_argument('--max-doc', type=int, default=60, help='docstring lines to print')
    args = ap.parse_args()
    root = find_stub_root(args.stubs)
    if root is None:
        print(SETUP_HINT)
        sys.exit(2)
    if args.areas:
        text, n = areas(root)
    elif args.area:
        text, n = list_area(root, args.area)
    elif args.search:
        text, n = search(root, args.search)
    elif args.grep:
        text, n = search(root, args.grep, in_docs=True)
    elif args.name:
        text, n = lookup(root, args.name, args.max_doc)
    else:
        ap.print_help()
        sys.exit(2)
    print(text)
    sys.exit(0 if n else 1)


if __name__ == '__main__':
    try:
        main()
    except BrokenPipeError:      # output piped into head/less
        sys.exit(0)
