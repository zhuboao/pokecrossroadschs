#!/usr/bin/env python3
"""
Migrate Chinese text from pokeemerald-expansion into pokecrossroads.

For each script file (map scripts, data/scripts/, data/text/),
find matching text labels and replace the English .string lines
with the expansion's Chinese .string lines.

Labels not found in expansion are left untouched (English).
"""

import os, re, sys
from pathlib import Path

EX_ROOT = Path("/home/leonardo/dev/pokeemerald-expansion")
CR_ROOT = Path("/home/leonardo/dev/pokecrossroads")

# ── Label detection ───────────────────────────────────────────────────────────
# A label line: starts at column 0, identifier, then one or two colons,
# optional whitespace, end of line.
LABEL_RE = re.compile(r'^([A-Za-z_]\w*):{1,2}\s*$')
STRING_RE = re.compile(r'^\s+\.string\s+"')

def is_string_line(line):
    return bool(STRING_RE.match(line))

def is_label_line(line):
    return bool(LABEL_RE.match(line))

def get_label(line):
    m = LABEL_RE.match(line)
    return m.group(1) if m else None

# ── Extract text blocks from a file ──────────────────────────────────────────
def extract_blocks(content):
    """
    Returns dict: label_name -> list of raw .string lines (stripped of newline).
    Only labels immediately followed by .string lines are included.
    """
    blocks = {}
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        label = get_label(lines[i])
        if label:
            # Collect consecutive .string lines
            j = i + 1
            string_lines = []
            while j < len(lines) and is_string_line(lines[j]):
                string_lines.append(lines[j])
                j += 1
            if string_lines:
                blocks[label] = string_lines
        i += 1
    return blocks

# ── Apply translations to a crossroads file ───────────────────────────────────
def apply_translations(cr_content, ex_blocks):
    """
    Walk crossroads content line by line.
    When a label is found whose text is in ex_blocks, replace the
    following .string lines with the expansion's (Chinese) version,
    using the same indentation as crossroads (usually a tab).
    """
    lines = cr_content.splitlines(keepends=True)
    result = []
    replaced = 0
    skipped = 0
    i = 0

    while i < len(lines):
        line = lines[i].rstrip('\n').rstrip('\r')
        label = get_label(line)

        if label:
            result.append(lines[i])
            i += 1

            # Collect the original .string block in crossroads
            cr_strings = []
            while i < len(lines) and is_string_line(lines[i].rstrip('\n').rstrip('\r')):
                cr_strings.append(lines[i])
                i += 1

            if cr_strings and label in ex_blocks:
                # Determine crossroads indentation (tab or spaces)
                indent = re.match(r'^(\s+)', cr_strings[0])
                indent = indent.group(1) if indent else '\t'

                # Write expansion's Chinese strings with crossroads indentation
                for ex_line in ex_blocks[label]:
                    # ex_line has expansion's indentation; strip and re-indent
                    content_part = ex_line.lstrip()
                    result.append(indent + content_part + '\n')
                replaced += 1
            else:
                # Keep original
                result.extend(cr_strings)
                if cr_strings:
                    skipped += 1
        else:
            result.append(lines[i])
            i += 1

    return ''.join(result), replaced, skipped

# ── Process a single file pair ────────────────────────────────────────────────
def process_file(ex_path, cr_path):
    ex_content = ex_path.read_text(encoding='utf-8')
    cr_content = cr_path.read_text(encoding='utf-8')

    ex_blocks = extract_blocks(ex_content)
    if not ex_blocks:
        return 0, 0

    new_content, replaced, skipped = apply_translations(cr_content, ex_blocks)

    if replaced > 0:
        cr_path.write_text(new_content, encoding='utf-8')

    return replaced, skipped

# ── Main ──────────────────────────────────────────────────────────────────────
total_replaced = 0
total_skipped = 0
files_modified = 0

file_sets = [
    # (glob pattern relative to repo root, description)
    ("data/maps/*/scripts.inc",   "Map scripts"),
    ("data/scripts/*.inc",        "Global scripts"),
    ("data/text/*.inc",           "System text"),
]

for pattern, desc in file_sets:
    cr_files = sorted(CR_ROOT.glob(pattern))
    batch_replaced = 0
    batch_skipped = 0
    batch_modified = 0

    for cr_path in cr_files:
        rel = cr_path.relative_to(CR_ROOT)
        ex_path = EX_ROOT / rel
        if not ex_path.exists():
            continue

        r, s = process_file(ex_path, cr_path)
        batch_replaced += r
        batch_skipped += s
        if r > 0:
            batch_modified += 1

    total_replaced += batch_replaced
    total_skipped += batch_skipped
    files_modified += batch_modified
    print(f"{desc}: {batch_modified} files modified, "
          f"{batch_replaced} labels translated, "
          f"{batch_skipped} labels kept (crossroads-only)")

print(f"\nTotal: {files_modified} files modified, "
      f"{total_replaced} labels translated, "
      f"{total_skipped} labels kept in English")
