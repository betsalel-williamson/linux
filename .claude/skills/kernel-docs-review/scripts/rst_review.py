#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Report-only documentation review signals for Documentation/ (RST + plain text).

This is a stand-in for `merlon review`, whose engine only reads Markdown.
It never edits files. It needs only the Python standard library (no Sphinx,
no docutils), so it runs anywhere the kernel tree is checked out.

Signals (Merlon-compatible names first, kernel-specific after):
  index-size          a toctree lists many entries with no :caption:
  long-shard          a document long enough that it may be doing two jobs
  duplicate-paragraph the same paragraph appears in more than one document
  similar-titles      documents in one directory share a title
  toctree-orphan      an .rst file no toctree, include, or :orphan: reaches
  undefined-ref       :ref:`label` with no matching ".. _label:" anywhere
  legacy-unrendered   .txt / extensionless prose that Sphinx never renders
  glossary-candidate  an acronym used across many subsystems, rarely expanded

Usage:
  rst_review.py [--root .] [--subdir Documentation/process] [--json]
                [--signals a,b] [--top N] [--include-translations]
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys

DOC = "Documentation"

# Directories whose files are structured data or generated, not prose.
NON_PROSE_DIRS = ("devicetree/bindings", "ABI/", "features/", "sphinx",
                  "sphinx-static", "sphinx-includes", "output/")
NON_PROSE_NAMES = {"Makefile", "Kconfig", "Kbuild", ".gitignore",
                   "dontdiff", "CREDITS", "conf.py", ".renames.txt",
                   "COPYING-logo"}
# Top-level one-line pointers kept for old links on purpose.
STUB_MAX_WORDS = 40

THRESH = {
    "index_entries": 30,     # entries in one uncaptioned toctree
    "long_words": 12000,     # kernel docs run long; Merlon default is 2500
    "dup_min_words": 40,
    "glossary_min_subsys": 8,
    "glossary_max_expanded": 0.10,
}

LABEL_DEF = re.compile(r"^\s*(?:[*-]\s+)?\.\.\s+_(?:`([^`]+)`|([^:`][^:]*?)):\s*$")
# Labels emitted by Sphinx itself or by Documentation/sphinx/*.py extensions.
GENERATED_LABEL = re.compile(r"^(genindex|modindex|search|maintainers|"
                             r"maintainers_table|abi_.*|netlink-.*)$")
NAME_OPT = re.compile(r"^\s+:name:\s*(\S.*?)\s*$")
REF_USE = re.compile(r":ref:`(?:[^`<]*<([^`>]+)>|([^`<]+))`")
DOC_USE = re.compile(r":doc:`(?:[^`<]*<([^`>]+)>|([^`<]+))`")
INCLUDE = re.compile(r"^\s*\.\.\s+(?:kernel-)?(?:include|literalinclude|"
                     r"kernel-feat|kernel-abi)::\s*(\S+)")
TOCTREE = re.compile(r"^(\s*)\.\.\s+toctree::")
ADORN = re.compile(r"^([=\-~^\"'`#*+.:_])\1{2,}\s*$")
ACRONYM = re.compile(r"\b([A-Z][A-Z0-9]{2,6})\b")
# Capitalised English, licence and boilerplate words that are not jargon.
ACRONYM_STOP = set("""
SPDX GPL LGPL GNU BSD MIT README TODO FIXME XXX NOTE NOT AND THE FOR ANY ALL
USE MUST SHALL SHOULD MAY THIS THAT WITH FROM YOU ARE NONE OFF SET GET PUT
READ WRITE DATA NAME MODE STATUS ERROR WARN BUG FILE PATH DEFAULT RESET BIT
DEVICE CONFIG ONLY NEW OLD END EOF TRUE FALSE YES HOWTO FAQ USA III IIC
""".split())
MARKUP = re.compile(r":[a-z:]+:`([^`<]*)(?:<[^`>]*>)?`|``([^`]*)``|[*`|]")


def rel(path, root):
    return os.path.relpath(path, root)


def is_prose_file(relpath):
    base = os.path.basename(relpath)
    if base in NON_PROSE_NAMES:
        return False
    sub = relpath[len(DOC) + 1:]
    if any(sub.startswith(d) for d in NON_PROSE_DIRS):
        return False
    ext = os.path.splitext(base)[1]
    return ext in (".rst", ".txt", "") or base.startswith("README")


def walk(root, include_translations):
    out = []
    for dp, dns, fns in os.walk(os.path.join(root, DOC)):
        dns[:] = [d for d in dns if not d.startswith(".")
                  and (include_translations or d != "translations")]
        for fn in fns:
            p = os.path.join(dp, fn)
            r = rel(p, root)
            if is_prose_file(r) and not os.path.islink(p):
                out.append(r)
    return sorted(out)


def read(root, r):
    try:
        with open(os.path.join(root, r), encoding="utf-8",
                  errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def title_of(text):
    lines = text.splitlines()
    for i in range(1, len(lines)):
        cur = lines[i].rstrip()
        prev = lines[i - 1].strip()
        if ADORN.match(cur) and prev and not ADORN.match(prev) \
                and len(cur) >= len(prev) - 1:
            return prev
    return None


def toctrees(text):
    """Yield (entries, caption, has_glob) for every toctree directive."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = TOCTREE.match(lines[i])
        if not m:
            i += 1
            continue
        base = len(m.group(1))
        entries, caption, glob = [], None, False
        i += 1
        while i < len(lines):
            ln = lines[i]
            if ln.strip() == "":
                i += 1
                continue
            ind = len(ln) - len(ln.lstrip())
            if ind <= base:
                break
            s = ln.strip()
            if s.startswith(":caption:"):
                caption = s[len(":caption:"):].strip()
            elif s.startswith(":glob:"):
                glob = True
            elif s.startswith(":"):
                pass
            elif not (s == ".." or s.startswith(".. ")):
                tm = re.match(r".*<([^>]+)>\s*$", s)
                entries.append(tm.group(1) if tm else s)
            i += 1
        yield entries, caption, glob


def resolve_doc(src_rel, target):
    """Resolve a toctree/:doc: target to a Documentation/ relative path stem."""
    target = target.strip()
    if target.startswith(("http:", "https:")):
        return None
    if target.startswith("/"):
        stem = os.path.normpath(os.path.join(DOC, target.lstrip("/")))
    else:
        stem = os.path.normpath(os.path.join(os.path.dirname(src_rel), target))
    return stem[:-4] if stem.endswith(".rst") else stem


def paragraphs(text):
    para = []
    for ln in text.splitlines() + [""]:
        if ln.strip() == "":
            if para:
                yield " ".join(para)
                para = []
        elif not ln.lstrip().startswith(".. ") and not ADORN.match(ln):
            para.append(ln.strip())


def norm(p):
    p = MARKUP.sub(lambda m: (m.group(1) or m.group(2) or ""), p)
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", p.lower())).strip()


def errno_names(root):
    names = set()
    for h in ("include/uapi/asm-generic/errno-base.h",
              "include/uapi/asm-generic/errno.h", "include/linux/errno.h"):
        try:
            with open(os.path.join(root, h), encoding="utf-8") as f:
                names.update(re.findall(r"#define\s+(E[A-Z0-9]+)\s", f.read()))
        except OSError:
            pass
    return names


def prose_only(text):
    """Drop literal blocks, code spans and directive bodies."""
    out, skip_ind = [], None
    for ln in text.splitlines():
        ind = len(ln) - len(ln.lstrip())
        if skip_ind is not None:
            if ln.strip() == "" or ind > skip_ind:
                continue
            skip_ind = None
        if ln.rstrip().endswith("::") or ln.lstrip().startswith(".. "):
            skip_ind = ind
            if ln.lstrip().startswith(".. "):
                continue
        out.append(ln)
    return re.sub(r"``[^`]*``|:[a-z:]+:`[^`]*`", " ", "\n".join(out))


def glossary_terms(texts):
    """Terms already owned by a '.. glossary::' (one Sphinx namespace)."""
    owned = {}
    for r, t in texts.items():
        if ".. glossary::" not in t:
            continue
        body = t.split(".. glossary::", 1)[1]
        base = None
        for ln in body.splitlines():
            if not ln.strip():
                continue
            ind = len(ln) - len(ln.lstrip())
            if base is None and not ln.lstrip().startswith(":"):
                base = ind
            if ind == 0:
                break
            if ind == base:
                owned.setdefault(ln.strip().lower(), r)
    return owned


def subsystem(r):
    parts = r.split("/")
    return parts[1] if len(parts) > 2 else "(top)"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--subdir", help="only report findings under this path")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--signals", help="comma list of signals to report")
    ap.add_argument("--top", type=int, default=15,
                    help="max findings per signal in text output")
    ap.add_argument("--include-translations", action="store_true")
    a = ap.parse_args()

    root = os.path.abspath(a.root)
    if not os.path.isdir(os.path.join(root, DOC)):
        sys.exit("run from the kernel tree root or pass --root")
    want = set(a.signals.split(",")) if a.signals else None
    files = walk(root, a.include_translations)
    texts = {r: read(root, r) for r in files}
    rst = [r for r in files if r.endswith(".rst")]
    rst_stems = {r[:-4] for r in rst}
    findings = []

    def add(sig, path, detail, **extra):
        findings.append(dict(signal=sig, path=path, detail=detail, **extra))

    # --- reachability: toctrees, includes, :orphan:, :doc: ---
    reached = {os.path.join(DOC, "index")}
    included = set()
    for r, t in texts.items():
        for ln in t.splitlines():
            im = INCLUDE.match(ln)
            if im:
                tgt = im.group(1)
                p = os.path.normpath(os.path.join(os.path.dirname(r), tgt)) \
                    if not tgt.startswith("/") else \
                    os.path.normpath(os.path.join(DOC, tgt.lstrip("/")))
                included.add(p)
        if not r.endswith(".rst"):
            continue
        for entries, caption, glob in toctrees(t):
            for e in entries:
                if glob and "*" in e:
                    pat = re.compile("^" + re.escape(resolve_doc(r, e))
                                     .replace(r"\*", "[^/]*") + "$")
                    reached.update(s for s in rst_stems if pat.match(s))
                else:
                    s = resolve_doc(r, e)
                    if s:
                        reached.add(s)
            if len(entries) >= THRESH["index_entries"] and not caption:
                add("index-size", r,
                    f"toctree lists {len(entries)} entries with no :caption:",
                    entries=len(entries))
        for m in DOC_USE.finditer(t):
            s = resolve_doc(r, m.group(1) or m.group(2))
            if s:
                reached.add(s)

    # .. maintainers-profile-toc:: builds a toctree from "P:" lines in
    # MAINTAINERS (Documentation/sphinx/maintainers_include.py).
    try:
        with open(os.path.join(root, "MAINTAINERS"), encoding="utf-8",
                  errors="replace") as f:
            for ln in f:
                if ln.startswith("P:") and DOC + "/" in ln:
                    reached.add(ln.split(None, 1)[1].strip()[:-4])
    except OSError:
        pass

    for r in rst:
        if r[:-4] in reached or r in included:
            continue
        if re.search(r"^:orphan:", texts[r], re.M):
            continue
        add("toctree-orphan", r,
            "not in any toctree, include, or :doc: link, and not :orphan:")

    for r in files:
        if r.endswith(".rst") or r in included:
            continue
        t = texts[r]
        if t.startswith("#!") or len(t.split()) <= STUB_MAX_WORDS:
            continue  # a script, or a deliberate redirect stub
        add("legacy-unrendered", r,
            "plain-text doc that Sphinx does not render (not .rst, not "
            "included)", words=len(texts[r].split()))

    # --- labels ---
    labels = set()
    for t in texts.values():
        for ln in t.splitlines():
            m = LABEL_DEF.match(ln)
            if m:
                labels.add((m.group(1) or m.group(2)).strip().lower())
            m = NAME_OPT.match(ln)
            if m:
                labels.add(m.group(1).lower())
    # sphinx.ext.autosectionlabel with autosectionlabel_prefix_document=True
    # (see Documentation/conf.py): "<docname>:<section title>".
    for r in rst:
        lines = texts[r].splitlines()
        stem = r[len(DOC) + 1:-4]
        for i in range(1, len(lines)):
            if ADORN.match(lines[i].rstrip()) and lines[i - 1].strip() \
                    and not ADORN.match(lines[i - 1].strip()):
                labels.add(f"{stem}:{lines[i - 1].strip()}".lower())
    for r in rst:
        for m in REF_USE.finditer(texts[r]):
            lab = re.sub(r"\s+", " ", (m.group(1) or m.group(2)).strip())
            if lab.lower() not in labels and not GENERATED_LABEL.match(lab) \
                    and "translations" not in r:
                add("undefined-ref", r, f":ref:`{lab}` has no '.. _{lab}:' "
                    "in the scanned tree (may be generated, e.g. kernel-doc)",
                    label=lab)

    # --- titles and length ---
    by_dir = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in files:
        t = texts[r]
        words = len(t.split())
        if words >= THRESH["long_words"]:
            add("long-shard", r, f"{words} words", words=words)
        ti = title_of(t)
        if ti:
            by_dir[os.path.dirname(r)][ti.strip().lower()].append(r)
    for d, m in by_dir.items():
        for ti, rs in m.items():
            if len(rs) > 1:
                add("similar-titles", d, f"{len(rs)} documents titled "
                    f"'{ti}'", files=rs)

    # --- duplicate paragraphs ---
    seen = collections.defaultdict(set)
    sample = {}
    for r in files:
        for p in paragraphs(texts[r]):
            n = norm(p)
            if len(n.split()) < THRESH["dup_min_words"]:
                continue
            h = hashlib.sha1(n.encode()).hexdigest()
            seen[h].add(r)
            sample.setdefault(h, p[:160])
    for h, rs in seen.items():
        if len(rs) > 1:
            rs = sorted(rs)
            add("duplicate-paragraph", rs[0],
                f"same paragraph in {len(rs)} documents: \"{sample[h]}...\"",
                files=rs)

    # --- glossary candidates ---
    use = collections.defaultdict(set)
    files_with = collections.defaultdict(set)
    expanded = collections.defaultdict(set)
    errnos = errno_names(root)
    owned = glossary_terms(texts)
    prose = {r: prose_only(texts[r]) for r in files}
    for r in files:
        for m in ACRONYM.finditer(prose[r]):
            ac = m.group(1)
            if ac in ACRONYM_STOP or ac in errnos or \
                    not re.search("[A-Z]", ac) or re.search(r"\d$", ac):
                continue
            use[ac].add(subsystem(r))
            files_with[ac].add(r)
    for ac, rs in files_with.items():
        if len(use[ac]) < THRESH["glossary_min_subsys"]:
            continue
        pat = re.compile(r"\(" + ac + r"s?\)|\b" + ac +
                         r"\s*(?:\(|stands for|means|is short for|--|:\s)"
                         r"\s*[A-Z][a-z]")
        for r in rs:
            if pat.search(prose[r]):
                expanded[ac].add(r)
        ratio = len(expanded[ac]) / len(rs)
        if ratio <= THRESH["glossary_max_expanded"]:
            add("glossary-candidate", ac,
                f"used in {len(rs)} files across {len(use[ac])} subsystems; "
                f"expanded in {len(expanded[ac])} ({ratio:.0%})"
                + (f"; already a glossary term in {owned[ac.lower()]}"
                   if ac.lower() in owned else ""),
                files=len(rs), subsystems=len(use[ac]),
                expanded=len(expanded[ac]), owned_by=owned.get(ac.lower()))

    # --- filter + report ---
    if a.subdir:
        sd = a.subdir.rstrip("/")
        findings = [f for f in findings if f["signal"] == "glossary-candidate"
                    or f["path"].startswith(sd)
                    or any(x.startswith(sd) for x in f.get("files", [])
                           if isinstance(f.get("files"), list))]
    if want:
        findings = [f for f in findings if f["signal"] in want]

    if a.json:
        json.dump(findings, sys.stdout, indent=1)
        print()
        return
    order = ["index-size", "long-shard", "duplicate-paragraph",
             "similar-titles", "toctree-orphan", "undefined-ref",
             "legacy-unrendered", "glossary-candidate"]
    by = collections.defaultdict(list)
    for f in findings:
        by[f["signal"]].append(f)
    print(f"scanned {len(files)} prose files ({len(rst)} .rst)")
    for s in order:
        fs = by.get(s, [])
        if not fs:
            continue
        key = {"long-shard": "words", "index-size": "entries",
               "glossary-candidate": "files"}.get(s)
        if key:
            fs.sort(key=lambda f: -f.get(key, 0))
        elif s == "duplicate-paragraph":
            fs.sort(key=lambda f: -len(f["files"]))
        print(f"\n## {s} ({len(fs)})")
        for f in fs[:a.top]:
            print(f"  {f['path']}: {f['detail']}")
            if s in ("duplicate-paragraph", "similar-titles"):
                for x in f["files"][:6]:
                    print(f"      - {x}")
        if len(fs) > a.top:
            print(f"  ... {len(fs) - a.top} more (use --json or --top)")


if __name__ == "__main__":
    main()
