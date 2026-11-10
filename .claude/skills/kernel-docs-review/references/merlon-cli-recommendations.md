# Merlon CLI: recommendations for RST and plain-text trees

Audience: the Merlon Docs maintainers. Evidence comes from reading
`@merlon-docs/merlon-docs-core` 1.1.0 `dist/index.js` and from running the
equivalent checks on the Linux kernel `Documentation/` tree (about 3,500 prose
files: 3,489 `.rst`, plus `.txt`, `README`, and extensionless files; zero
`.md`).

## What blocks use today

| Where in core                                | Assumption                                         | Effect on an RST tree                         |
| -------------------------------------------- | -------------------------------------------------- | --------------------------------------------- |
| `globSync("**/*.md")` in coverage and review | shards are Markdown                                | every file is invisible; review reports nothing |
| `manifest = "index.md"`, `shards.md`         | the guide index is a Markdown link list            | `index.rst` toctrees are not read             |
| `[text](#slug)` + `refs.json`                | links are Markdown fragments, slugs from headings  | `:ref:`, `:doc:`, labels, `:term:` ignored    |
| `#` headings, demoted on compile             | ATX headings                                       | RST adornment headings not parsed             |
| `compile` writes `docs/_build/*.md`          | Merlon is the build                                | the tree already has a build (Sphinx)         |
| config must sit under the docs root          | the project accepts a new config file              | an upstream that refuses tooling files cannot adopt it |

## Requests, in priority order

1. **Review-only mode with no compile step.** `merlon review --no-compile
   --source <dir>` should report the four signals against an existing tree
   built by another tool. Teams with Sphinx, MkDocs, or Antora keep their build
   and get just the sprawl signals.
2. **Pluggable source formats.** A `formats` setting (`markdown`, `rst`,
   `plaintext`) that controls globbing, paragraph splitting, title detection,
   and link extraction. For RST: heading adornment, `.. _label:`, the
   `:name:` option, `:ref:`/`:doc:`/`:term:`, and `.. include::`. For plain
   text: blank-line paragraphs and a first-line or underlined title.
3. **Toctree as manifest.** Read `.. toctree::` entries, `:caption:` (counts
   as an index group for `index-size`) and `:glob:`. Allow a manifest plugin,
   because projects generate toctrees (the kernel's
   `.. maintainers-profile-toc::` builds one from `MAINTAINERS` `P:` lines).
4. **Cross-reference registry for Sphinx.** Build the label set from explicit
   labels, `:name:` options, and autosectionlabel (`docname:Section Title`,
   honouring `autosectionlabel_prefix_document` and `maxdepth`). Allow an
   ignore pattern for labels generated at build time (`genindex`, `abi_*`,
   `netlink-*` in the kernel). Better still, read Sphinx's `objects.inv`
   after a build instead of re-implementing resolution.
5. **Glossary awareness.** Detect `.. glossary::` blocks, report terms defined
   twice across the build (Sphinx glossary terms are global), and report
   frequent terms that never link with `:term:`. Ship an errno and English
   capitalised-word stoplist for acronym detection; without one, the top
   candidates are `EINVAL`, `NOT`, and `MUST`.
6. **Config outside the tree.** Accept `--config` from any path, with
   `--docs-root` pointing elsewhere, so the tool can run against a project
   without committing anything to it.
7. **Owner-aware review.** An optional hook that maps a file to its owner
   (`CODEOWNERS`, or a command such as `scripts/get_maintainer.pl -f`).
   `duplicate-paragraph` across different owners is usually intentional
   (self-contained per-driver pages) and should be reported separately from
   duplicates under one owner, which are true sprawl.
8. **Per-signal thresholds per guide.** Reference pages run long on purpose.
   `review.maxShardWords` should be overridable per guide or glob.
9. **Skill text.** The getting-started workflow's brownfield path scaffolds
   `docs/` beside legacy docs. Add a "brownfield, foreign format" branch that
   instead installs a project-local extension skill and runs review only, as
   this repository does.

## Reference implementation

`.claude/skills/kernel-docs-review/scripts/rst_review.py` in this fork
implements items 1 to 5 for one tree in under 500 lines of
stdlib Python. It can be offered as test fixtures or as a starting point.
