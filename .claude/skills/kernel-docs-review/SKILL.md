---
name: kernel-docs-review
description: >-
  Linux-kernel extension for the vendored merlon-docs skill. Load it together
  with merlon-docs for any work under Documentation/ in this tree: reviewing
  docs, finding weak or stale pages, glossary work, cross-reference fixes, or
  preparing a documentation patch. It maps Merlon Docs concepts onto the
  kernel's Sphinx/reStructuredText system, overrides Merlon defaults that do
  not fit a legacy kernel tree, and sets the value bar a change must clear
  before anyone sends it upstream.
license: MIT
metadata:
  extends: merlon-docs
  scope: fork-local tooling; never part of an upstream patch
---

# Kernel docs review (merlon-docs extension)

`merlon-docs` (vendored under `.agents/skills/merlon-docs/`, do not edit it)
supplies the workflow: four review lenses, decide-each-finding, atomic commit
groups, "current docs only", "one rule in one place". This skill supplies the
kernel context. **Where the two conflict, this skill wins**, because Merlon
assumes a Markdown `docs/` tree that this repository does not have and must
not gain.

Read before any kernel work (AGENTS.md requires it):
`Documentation/process/coding-assistants.rst`,
`Documentation/process/generated-content.rst`,
`Documentation/process/submitting-patches.rst`,
`Documentation/doc-guide/index.rst`.

## Hard rules (kernel overrides)

- **Never** scaffold `docs/`, add `merlon.config.json`, add `.md` files, or
  run Merlon's getting-started workflow here. Merlon's brownfield path
  ("scaffold the four tiers alongside legacy docs") is **not** used. The
  existing `Documentation/` tree is the system of record.
- **Never** run `merlon compile`/`check`/`fix`/`review` on `Documentation/`:
  the engine only globs `**/*.md` and sees none of the ~3,500 prose files.
  Use the kernel-native equivalents below.
- **Never** add `Signed-off-by`. Only the human submitter certifies the DCO.
- **Never** send mail, post to lore, or open upstream anything. Draft only;
  the human reviews and sends.
- **Never** edit `Documentation/translations/` except at a translation
  maintainer's request; translations track the English file via
  `tools/docs/checktransupdate.py`.
- **Never** ship anything under `.agents/`, `.claude/`, or `skills-lock.json`
  in an upstream patch. They are fork-local (the kernel `.gitignore` hides
  dotfiles for this reason; they were force-added to this fork on purpose).
- **Always** verify a claim against the code at a named commit before calling
  a doc wrong (grep the symbol, read the Kconfig, check the header).
  Memory and model knowledge are not evidence.
- **Always** state tool use in the changelog per `generated-content.rst`:
  what tool, what input, which parts it produced, how it was checked.

## Concept map

| Merlon Docs              | In this tree                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------ |
| shard                    | one `.rst` document (legacy: `.txt`, `README`, extensionless)                                                |
| guide                    | a book: top-level `Documentation/<dir>/` with its own `index.rst`                                            |
| guide index (`index.md`) | `index.rst` `.. toctree::` (entries, `:caption:`, `:glob:`); `.. maintainers-profile-toc::` reads MAINTAINERS |
| `merlon compile`         | `make htmldocs` (subset: `make SPHINXDIRS="process" htmldocs`)                                               |
| `merlon check`           | Sphinx warnings + `tools/docs/documentation-file-ref-check` + `tools/docs/find-unused-docs.sh` + `scripts/checkpatch.pl` |
| `merlon refs`            | `.. _label:`, `:name:`, `:ref:`, `:doc:`, autosectionlabel `doc/path:Section Title`, plain `Documentation/x/y.rst` text (auto-linked by `Documentation/sphinx/automarkup.py`) |
| `merlon review`          | `scripts/rst_review.py` in this skill (same four signals plus kernel ones)                                    |
| `docs/glossary/`         | a `.. glossary::` directive; link with `:term:`. Terms share one namespace across the whole build             |
| tier: client             | `admin-guide/`, `userspace-api/`, per-driver user pages                                                      |
| tier: features           | `core-api/`, `driver-api/`, subsystem design docs                                                            |
| tier: developer          | `process/`, `doc-guide/`, `dev-tools/`, `maintainer/`                                                        |
| ADR / design history     | the commit message and the lore thread; docs state current behaviour only                                    |
| changeset / CHANGELOG    | the commit log; there is no changelog file                                                                    |
| owner of a shard         | `scripts/get_maintainer.pl -f <file>` (and the `P:` profile for that subsystem)                               |

## Review procedure (replaces Merlon doc-review Step 1)

From the tree root:

```bash
python3 -I .claude/skills/kernel-docs-review/scripts/rst_review.py --subdir Documentation/<book>
```

```bash
tools/docs/documentation-file-ref-check
```

```bash
make SPHINXDIRS="<book>" htmldocs 2>&1 | grep -E 'WARNING|ERROR'
```

Sphinx setup: a venv from `Documentation/sphinx/requirements.txt` on
`PATH`, and `make O=<scratch dir> htmldocs SPHINXOPTS=-j4` so output stays
out of the tree. The kernel wrapper runs Sphinx quietly; a finished build has
`Documentation/output/index.html` under the `O=` dir and no "build
succeeded" line. The baseline full build had 69 unique warnings (see
`reports/`), so a new warning stands out.

Signals from `rst_review.py` (report-only, stdlib Python, ~10 s for the tree):

| Signal               | Kernel default decision                                                                                               |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `index-size`         | **Leave** unless the book's maintainer has asked for grouping; alphabetical driver lists are a deliberate layout       |
| `long-shard`         | **Leave** for reference pages (`kvm/api.rst`, `kernel-parameters.txt`); split only on a second audience or job        |
| `duplicate-paragraph`| **Leave** across per-driver pages (hwmon, IIO, Ethernet): each is read alone and owned by a different maintainer. Act only when two pages under one owner state one rule differently |
| `similar-titles`     | **Reword** when siblings are different things (e.g. NTB vs vNTB); **Leave** when an `index.rst` repeats its only child |
| `toctree-orphan`     | **Link** into the right toctree, or `:orphan:` if intentional                                                          |
| `undefined-ref`      | **Fix** (rare: Sphinx already warns)                                                                                   |
| `legacy-unrendered`  | **Leave** unless the owner wants conversion; flag only a `.txt` that has an `.rst` sibling on the same topic          |
| `glossary-candidate` | See the glossary bar below; generic industry acronyms are **out**                                                      |

### Check for prior work before proposing anything

A finding is not a patch candidate until all of these are checked, and the
report records which ones were reachable:

1. **linux-next** (merges `docs-next` and the subsystem trees):
   `git fetch --depth=1 https://git.kernel.org/pub/scm/linux/kernel/git/next/linux-next.git master:refs/remotes/next/master`,
   then `git grep` the offending text in `next/master`. Do **not** run the
   linux-next build here (it executes fetched Sphinx extensions); compare
   sources statically, and leave a linux-next docs build to the human.
2. **lore** (`https://lore.kernel.org/all/?q=<file or phrase>`): the only
   place docs-only patches to linux-doc are visible.
3. **Patchwork** (`https://patchwork.kernel.org/api/patches/?q=<subject words>`):
   subject search across subsystem lists. linux-doc is **not** a project
   there.
4. **Bugzilla** (`https://bugzilla.kernel.org/rest/bug?product=Documentation&resolution=---`):
   mostly man-pages; scan for `Documentation/` paths. Reader reports there
   are good evidence of reader harm (value bar item 1).

If a patch already exists, do not write another: review it, or ask its
maintainer what it needs. If an active series touches the same file, raise
the finding in review of that series instead of sending a conflicting
patch. A source you could not reach makes the finding **unchecked**, not
**clear**.

Then read with the four Merlon lenses, but weight them for this tree:
**staff engineer first** (is it true of the code today?), then technical
writer, product manager, designer. Navigation complaints rarely land; factual
corrections do.

## The value bar (every proposed change must pass all five)

Write these answers into the finding before drafting anything. If one is
weak, drop the change.

1. **Reader harm today:** who is misled or blocked, and how? ("`get_maintainer.pl`
   routes binding patches to nobody" passes; "reads more smoothly" fails.)
2. **Evidence:** the code, Kconfig, header, or tool output at commit `<sha>`
   that proves the doc is wrong or missing. Quote the path and line.
3. **Owner:** the `get_maintainer.pl` output for the file and the list the
   patch would go to. One subsystem per patch.
4. **Reviewer cost:** small, one logical change, mechanically checkable.
   Prefer a diff a maintainer can verify in under five minutes.
5. **No churn:** no whitespace, wording-only, or style passes; no
   `.txt`→`.rst` conversions or file moves nobody asked for; no
   "AI-polished" rewrites of prose that is correct.

Rejected categories, even if a tool flags them: consolidating per-driver
boilerplate; generic acronym glossaries (CPU, API, USB, PCI); reflowing long
reference pages; renaming files; adding cross-links for their own sake.

## Glossary bar

A term earns an entry when **all** hold:

- it is kernel-specific (not in a general computing dictionary with the
  same meaning), e.g. *user context*, *softirq*, *merge window*, *folio*;
- it is used in three or more books without a local definition;
- a definition already exists somewhere in the tree that can be reused, or
  the code states the meaning precisely enough to write one and cite it;
- the term is **not** already defined by another `.. glossary::` (check with
  `rst_review.py --signals glossary-candidate`, which marks owned terms).
  Sphinx glossary terms are global; a second definition is a build warning.

Prefer upgrading an existing glossary (for example the plain definition list
at the end of `kernel-hacking/locking.rst`) to a `.. glossary::` directive
over creating a new file. That makes every term linkable with `:term:`
without adding prose.

## Writing the patch (when the human asks for one)

Follow `submitting-patches.rst`: subject `docs: <area>: <imperative>` (or the
subsystem's prefix from `git log --oneline -- <file>`), body explains the
reader harm and the evidence, then a tool-use paragraph, no `Signed-off-by`.
Run `scripts/checkpatch.pl --strict` on the result and the relevant
`make SPHINXDIRS=... htmldocs` with no new warnings. State anything you could
not build or test.

## Related

- `references/merlon-cli-recommendations.md`: upstream requests so the
  Merlon CLI can serve RST and plain-text trees directly.
- `reports/`: dated baseline reviews of this tree (snapshots, not durable docs).
