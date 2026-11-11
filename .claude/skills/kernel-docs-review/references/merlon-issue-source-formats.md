# Support documentation sources beyond GitHub Flavored Markdown (source-format adapters)

## Summary

Merlon Docs' workflow (shard responsibility, review lenses, sprawl signals,
"one rule in one place") is format-agnostic, but the engine in
`@merlon-docs/merlon-docs-core` assumes GitHub Flavored Markdown at every
layer: discovery, manifests, headings, links, slugs, and compile output.
Projects whose docs are reStructuredText (Sphinx), plain text, or AsciiDoc
cannot run `merlon review` or `merlon check` at all, even in report-only
mode.

This issue proposes making GFM **one source format among several**, behind
a small adapter interface, plus a review-only mode that works against a tree
built by another tool.

## Motivation: a real brownfield case

I tried to adopt the `merlon-docs` skill on the Linux kernel's
`Documentation/` tree: about 3,500 prose files (3,489 `.rst`, plus `.txt`,
`README`, and extensionless files), **zero `.md`**, built with Sphinx.

- `merlon review` and `merlon check` found nothing, because no file matched
  `**/*.md`.
- The getting-started workflow's brownfield path (scaffold `docs/` beside
  the legacy docs) is not an option for a project like this; upstream would
  not accept a parallel docs tree or a new config file.
- The skill's guidance was still valuable. I reimplemented the four
  `merlon review` signals for RST and plain text in about 450 lines of
  stdlib Python (see [Prototype](#prototype)). On the kernel tree it
  produced useful, verifiable findings in about 10 seconds. The ideas
  transfer; only the engine is format-locked.

## Where GFM is assumed (core 1.1.0, `dist/index.js`)

| Layer | Code | Assumption |
| ----- | ---- | ---------- |
| Discovery | `computeCoverage`, `guideScanDirs` consumers: `globSync("**/*.md")`; manifest fallback `readdirSync(...).filter(n => n.endsWith(".md"))` | shards are `.md` |
| Manifest | `isIndexFile` (`index.md`, `shards.md`), `assembleGuideUnmarked`, `resolveManifestPaths` | a guide index is a Markdown link list |
| Headings | `parseAtxHeading`, `parseHeading`, `isHeading`, `demoteHeadings`, `extractFirstHeading` | ATX `#` headings |
| Links | `scanMarkdownLinks`, `extractLinks`, `mdLinkPaths`, `slugLinkTargets`, `rewriteMarkdownLinkLines` | `[text](target#frag)` |
| Slugs / refs | `githubSlugify`, `buildSlugRegistry`, `refs.json` | anchors are GitHub heading slugs |
| Paragraphs | `createCodeFenceScanner`, `interruptsParagraph` | fenced code blocks, GFM block rules |
| Output | `defaultGuideOutputFile` → `${guide}.md`, copy step filters `.md` | compiled output is Markdown |

## Proposal

### 1. A `SourceFormat` adapter interface

Each format implements only what the engine already does for Markdown:

```ts
interface SourceFormat {
  id: string;                       // "gfm", "rst", "plaintext", "asciidoc"
  extensions: string[];             // [".rst"], [".txt", ""], ...
  isIndex(path: string): boolean;   // index.md | index.rst | index.adoc
  manifestEntries(text, path): string[];   // toctree / link list / include::
  title(text): string | null;
  headings(text): Heading[];        // level, text, line
  paragraphs(text): Paragraph[];    // prose only: code/literal blocks removed
  links(text, path): Link[];        // kind: file | anchor | label | external
  labels(text, path): string[];     // explicit targets this file defines
  wordCount(text): number;
}
```

GFM becomes the first adapter, extracted from the existing code with no
behavior change. Config selects adapters per guide or glob:

```json
{
  "sources": [
    { "glob": "**/*.md", "format": "gfm" },
    { "glob": "**/*.rst", "format": "rst" },
    { "glob": "**/*.txt", "format": "plaintext" }
  ]
}
```

Default: `[{ "glob": "**/*.md", "format": "gfm" }]`, so existing projects
see no change.

### 2. Review-only mode for trees built elsewhere

`merlon review --no-compile` (and a `check` subset) runs the signals
directly on sources. Projects keep Sphinx, MkDocs, Antora, or Docusaurus as
the build and use Merlon for sprawl detection and cross-reference checks.
`compile` stays GFM-only until someone needs more.

### 3. Pluggable reference resolution

Cross-reference rules differ by toolchain. Proposed resolvers:

- **gfm**: today's slug registry.
- **sphinx**: explicit labels (`.. _label:`), the `:name:` directive option,
  `:ref:` / `:doc:` / `:term:`, and `sphinx.ext.autosectionlabel`
  (`docname:Section Title`, honouring `autosectionlabel_prefix_document` and
  `autosectionlabel_maxdepth`). Better still: read `objects.inv` after the
  project's own build instead of reimplementing resolution.
- An `ignoreLabels` pattern for targets generated at build time (the kernel
  needs `genindex`, `abi_*`, `netlink-*`, `maintainers`).

### 4. Manifest plugins

Some projects generate toctrees. The kernel's `.. maintainers-profile-toc::`
builds one from `P:` lines in a `MAINTAINERS` file. A manifest hook (a
module that returns extra reachable paths) keeps orphan detection accurate
without hard-coding any one project.

### 5. Config outside the docs tree

Accept `--config` from any path with `--docs-root` pointing elsewhere, so a
project can be reviewed without committing anything to it. This matters
for large upstreams that will not take tooling files.

## Signals that need small format-aware tweaks

| Signal | GFM today | Needed for RST / text |
| ------ | --------- | --------------------- |
| `index-size` | links under one heading | toctree entries; `:caption:` counts as a group |
| `long-shard` | word count | same, but a per-glob `maxShardWords` (reference pages run long on purpose) |
| `duplicate-paragraph` | GFM paragraphs | adapter `paragraphs()`; strip roles and inline literals before hashing |
| `similar-titles` | first `#` heading | adapter `title()` (RST over/underline adornment) |

Two signals the prototype found useful that core could add for every
format: **orphan** (a source no manifest, include, or link reaches) and
**glossary-candidate** (a term used across many guides but never defined or
linked; needs an errno/English-caps stoplist to be usable).

## Acceptance criteria

- [ ] GFM behavior unchanged: existing fixtures and snapshot tests pass with
      the GFM adapter extracted.
- [ ] `merlon review --no-compile` on an RST fixture reports all four
      signals with file and line.
- [ ] Orphan detection follows `toctree` entries (relative, absolute `/`,
      `:glob:`), `.. include::`, `:doc:` links, and `:orphan:`.
- [ ] A `:ref:` to an autosectionlabel target or a `:name:` option does not
      report as broken.
- [ ] A plain-text adapter treats blank-line paragraphs and an underlined
      first heading as structure, and skips files that start with `#!`.
- [ ] `--config` outside the docs root works for `review` and `check`.
- [ ] Skill: the getting-started workflow gains a "brownfield, non-Markdown"
      branch that installs a project-local extension skill and runs review
      only, with no scaffold.

## Non-goals

- Converting RST or AsciiDoc to Markdown.
- Compiling non-Markdown shards into guides (Sphinx and friends already do
  this).
- Full RST parsing: line-level heuristics like the ones above are enough for
  review signals. `docutils` stays optional.

## Prototype

A stdlib-only Python stand-in for `merlon review` on RST and plain text,
written against the Linux kernel tree, is available as a reference and as a
source of fixtures:

- `rst_review.py`: implements items 1–4 above for one tree (toctree
  manifests, autosectionlabel and `:name:` labels, `MAINTAINERS`-driven
  toctrees, generated-label ignore list, errno-aware glossary candidates).
- False positives it hit and fixed are the most useful test cases: `../`
  toctree entries mistaken for comments, labels in list items and
  backquoted labels, `:ref:` text wrapped across lines, and symlinked docs
  double-counted as duplicates.

Happy to contribute fixtures or the GFM-adapter extraction if the direction
looks right.
