#!/usr/bin/env python3
"""
Migrate move .name and .description fields from expansion (Chinese)
into crossroads' moves_info.h, matching by [MOVE_XXX] constant names.
Also replaces shared description constants at the top of the file.

Handles #if/#else/#endif inside description blocks by skipping them.
"""
import re

EX_PATH = "/home/leonardo/dev/pokeemerald-expansion/src/data/moves_info.h"
CR_PATH = "/home/leonardo/dev/pokecrossroads/src/data/moves_info.h"

def read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

# ── Shared description constants ─────────────────────────────────────────────
# Match: (static )? const u8 sFooDescription[] = _( ... );
# We handle the _( ... ) body carefully to find the matching closing paren.

SHARED_DECL_RE = re.compile(
    r'((?:static\s+)?const\s+u8\s+(\w+)\[\]\s*=\s*_\()(.*?)(\);)',
    re.DOTALL
)

def extract_shared_consts(src):
    return {m.group(2): m.group(3) for m in SHARED_DECL_RE.finditer(src)}

def apply_shared_consts(cr_src, ex_consts):
    def replacer(m):
        varname = m.group(2)
        if varname in ex_consts:
            return m.group(1) + ex_consts[varname] + m.group(4)
        return m.group(0)
    return SHARED_DECL_RE.sub(replacer, cr_src)

# ── Per-move data ─────────────────────────────────────────────────────────────

NAME_RE = re.compile(r'(\.name\s*=\s*COMPOUND_STRING\(")([^"]*?)("\))')

# Matches the whole description field - both inline and variable-reference forms.
# Inline: .description = COMPOUND_STRING( ... )
# Var:    .description = sFooDescription,
DESC_VAR_RE = re.compile(r'\.description\s*=\s*(\w+Description)\b')

def find_compound_string_end(text, start):
    """
    Given text and the position of the opening '(' of COMPOUND_STRING(...),
    find the position of the matching closing ')'.
    Returns end index (exclusive, pointing after ')'), or -1 if not found or
    if the content contains preprocessor directives (#if/#else/#endif).
    """
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        elif ch == '#':
            # preprocessor directive inside - skip this description
            return -1
        i += 1
    return -1

def extract_move_data(src):
    """
    Returns dict: MOVE_CONSTANT ->
        {'name': str or None,
         'desc': str or None,   # raw content inside COMPOUND_STRING()
         'desc_type': 'inline'|'var'|None}
    """
    # Split into move entries by [MOVE_XXX] = {
    # We process the file character by character to handle nested braces.
    result = {}
    entry_re = re.compile(r'\[(MOVE_\w+)\]\s*=\s*\{')

    pos = 0
    while pos < len(src):
        m = entry_re.search(src, pos)
        if not m:
            break
        key = m.group(1)
        body_start = m.end()  # just after the opening {

        # Find the matching closing }
        depth = 1
        i = body_start
        while i < len(src) and depth > 0:
            if src[i] == '{':
                depth += 1
            elif src[i] == '}':
                depth -= 1
            i += 1
        body = src[body_start:i-1]
        pos = i

        # Extract .name
        nm = NAME_RE.search(body)
        name = nm.group(2) if nm else None

        # Extract .description
        desc = None
        desc_type = None

        var_m = DESC_VAR_RE.search(body)
        if var_m:
            desc = var_m.group(1)
            desc_type = 'var'
        else:
            # Look for .description = COMPOUND_STRING(
            cs_start = body.find('.description')
            if cs_start != -1:
                paren_pos = body.find('COMPOUND_STRING(', cs_start)
                if paren_pos != -1:
                    open_paren = paren_pos + len('COMPOUND_STRING')
                    # open_paren points at '('
                    end = find_compound_string_end(body, open_paren)
                    if end != -1:
                        desc = body[open_paren:end]  # includes ( and )
                        desc_type = 'inline'

        result[key] = {'name': name, 'desc': desc, 'desc_type': desc_type}

    return result

def apply_move_data(cr_src, ex_data):
    replaced_name = 0
    replaced_desc = 0
    skipped_desc_conditional = 0
    skipped_no_data = 0

    entry_re = re.compile(r'(\[(MOVE_\w+)\]\s*=\s*\{)')
    result_parts = []
    pos = 0

    while pos < len(cr_src):
        m = entry_re.search(cr_src, pos)
        if not m:
            result_parts.append(cr_src[pos:])
            break

        # Append everything up to (and including) the entry header
        result_parts.append(cr_src[pos:m.end()])
        key = m.group(2)
        body_start = m.end()

        # Find matching closing }
        depth = 1
        i = body_start
        while i < len(cr_src) and depth > 0:
            if cr_src[i] == '{':
                depth += 1
            elif cr_src[i] == '}':
                depth -= 1
            i += 1
        body = cr_src[body_start:i-1]
        closing = cr_src[i-1:i]  # the }
        pos = i

        if key not in ex_data:
            skipped_no_data += 1
            result_parts.append(body)
            result_parts.append(closing)
            continue

        ex = ex_data[key]

        # ── Replace .name ──
        if ex['name'] is not None:
            new_body = NAME_RE.sub(
                lambda nm: nm.group(1) + ex['name'] + nm.group(3),
                body
            )
            if new_body != body:
                replaced_name += 1
            body = new_body

        # ── Replace .description ──
        if ex['desc_type'] == 'var':
            # Expansion uses a named variable. Crossroads may use inline or var.
            # Try replacing var reference first.
            new_body = DESC_VAR_RE.sub(
                lambda dv: '.description = ' + ex['desc'],
                body, count=1
            )
            if new_body != body:
                replaced_desc += 1
                body = new_body
            else:
                # Crossroads uses inline - find and replace COMPOUND_STRING content
                cs_start = body.find('.description')
                if cs_start != -1:
                    paren_pos = body.find('COMPOUND_STRING(', cs_start)
                    if paren_pos != -1:
                        open_paren = paren_pos + len('COMPOUND_STRING')
                        end = find_compound_string_end(body, open_paren)
                        if end == -1:
                            skipped_desc_conditional += 1
                        else:
                            # Replace the inline COMPOUND_STRING with var reference
                            body = (body[:cs_start] +
                                    '.description = ' + ex['desc'] +
                                    body[end:])
                            replaced_desc += 1

        elif ex['desc_type'] == 'inline' and ex['desc'] is not None:
            # Expansion uses inline COMPOUND_STRING.
            # Check if crossroads uses var reference.
            var_m = DESC_VAR_RE.search(body)
            if var_m:
                # Keep var reference - the shared const will be updated separately
                pass
            else:
                cs_start = body.find('.description')
                if cs_start != -1:
                    paren_pos = body.find('COMPOUND_STRING(', cs_start)
                    if paren_pos != -1:
                        open_paren = paren_pos + len('COMPOUND_STRING')
                        end = find_compound_string_end(body, open_paren)
                        if end == -1:
                            skipped_desc_conditional += 1
                        else:
                            body = (body[:open_paren] +
                                    ex['desc'] +
                                    body[end:])
                            replaced_desc += 1

        result_parts.append(body)
        result_parts.append(closing)

    print(f"  Names replaced:         {replaced_name}")
    print(f"  Descriptions replaced:  {replaced_desc}")
    print(f"  Skipped (conditional):  {skipped_desc_conditional}")
    print(f"  Skipped (not in EX):    {skipped_no_data}")
    return "".join(result_parts)

# ── Main ──────────────────────────────────────────────────────────────────────
print("Reading files...")
ex_src = read_file(EX_PATH)
cr_src = read_file(CR_PATH)

print("Extracting shared description constants from expansion...")
ex_consts = extract_shared_consts(ex_src)
print(f"  Found {len(ex_consts)} shared constants")

print("Applying shared constants to crossroads...")
cr_src = apply_shared_consts(cr_src, ex_consts)

print("Extracting move data from expansion...")
ex_data = extract_move_data(ex_src)
print(f"  Found {len(ex_data)} move entries")

print("Applying move names/descriptions to crossroads...")
cr_src = apply_move_data(cr_src, ex_data)

print("Writing output...")
with open(CR_PATH, "w", encoding="utf-8") as f:
    f.write(cr_src)
print("Done.")
