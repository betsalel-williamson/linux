# Baseline docs review at 067c5c24cef2

Snapshot of `Documentation/` at commit `067c5c24cef2` (around v7.4-rc2).
Tools: `scripts/rst_review.py` from this skill,
`tools/docs/documentation-file-ref-check`, and manual verification against
the source tree. Sphinx was not run (docutils not installed in the review
environment), so Sphinx build warnings are not covered here.

## Headline

The kernel's docs are **structurally healthy**: zero toctree orphans, zero
unresolved `:ref:` labels, 16 dangling file references (most in
translations). The weaknesses are not structure. They are:

1. **Stale facts** in long-lived pages nobody owns closely.
2. **Path drift** after devicetree `.txt`→`.yaml` conversions, which breaks
   `MAINTAINERS` routing, not just links.
3. **Vocabulary without a home**: kernel-specific terms used across 10–20
   books, defined (if at all) in one buried page that nothing can link to.

Restructuring, de-duplicating, and splitting would add churn without much
benefit to readers, so we leave those alone.

## Mechanical signals (whole tree, translations excluded)

| Signal              | Count | Verdict |
| ------------------- | ----: | ------- |
| toctree-orphan      | 0     | healthy (all reached via toctree, `:doc:`, or MAINTAINERS `P:`) |
| undefined-ref       | 0     | healthy |
| dangling file refs  | 16    | 4 outside translations; see findings 1–3 |
| similar-titles      | 9     | 2 worth fixing (finding 5); 7 are index pages repeating their child: leave |
| duplicate-paragraph | 142   | 18 cross-book. Almost all are self-contained per-driver pages (hwmon, IIO, Intel Ethernet, fbdev, CXL examples): leave |
| index-size          | 12    | `hwmon/index.rst` has 290 uncaptioned entries; alphabetical by design: leave |
| long-shard          | 18    | reference pages (`virt/kvm/api.rst` 48k words, `kernel-parameters.txt` 43k): leave |
| legacy-unrendered   | 8     | leave; one `.txt`/`.rst` pair noted (finding 6) |
| glossary-candidate  | 111   | mostly generic acronyms (out of bar); see finding 4 |

## Findings that clear the value bar

Each lists reader harm, evidence, and owner (from `get_maintainer.pl`).

### 1. MAINTAINERS `F:` points at a removed binding (high value)

- **Harm:** `get_maintainer.pl` matches nothing for the binding, so patches to
  the MegaChips bridge binding are not routed to its two listed maintainers.
- **Evidence:** `MAINTAINERS:17260` names
  `bindings/display/bridge/megachips-stdpxxxx-ge-b850v3-fw.txt`; the tree has
  `megachips,stdp2690-ge-b850v3-fw.yaml` instead.
- **Fix:** one-line `F:` update. Owner: the entry's `M:` lines, plus the DT list.

### 2. Source comments citing converted DT bindings (low cost, low risk)

- `arch/arm/xen/enlighten.c:254` cites `bindings/arm/xen.txt`; the file is now
  `bindings/arm/xen.yaml`. Owner: XEN HYPERVISOR ARM.
- `arch/powerpc/sysdev/mpic.c:1108` cites `bindings/powerpc/fsl/mpic.txt`. The
  likely successor is `interrupt-controller/chrp,open-pic.yaml`, **unverified**:
  ask the powerpc maintainers before changing it.
- `bindings/regulator/siliconmitus,sm5703-regulator.yaml` references
  `bindings/mfd/siliconmitus,sm5703.yaml`, which does not exist. Needs the
  binding author; not a doc-only fix.

### 3. Translation path drift (leave to translators)

12 dangling references are under `Documentation/translations/` (two are
intentional `xxx` placeholders in `zh_CN/how-to.rst`). Report the rest to the
translation maintainers; do not patch.

### 4. The locking glossary is stale and cannot be linked (best glossary step)

`Documentation/kernel-hacking/locking.rst` ends with a 12-term glossary
(preemption, bh, hardirq, interrupt context, SMP, softirq, tasklet, timer, UP,
user context, userspace). It is a plain definition list, so no other page can
`:term:` link to it, and two entries are out of date:

- **bh:** "Bottom halves are deprecated, and will eventually be replaced by
  tasklets." Classic bottom halves are gone (`mark_bh` has 0 hits in
  `*.c`/`*.h`). The `_bh` suffix meaning "software interrupts" is still
  correct and is the useful part.
- **preemption:** narrates 2.5-era history, and says non-preemption applies
  "when `CONFIG_PREEMPT` is unset". `kernel/Kconfig.preempt:22-25` now makes
  `PREEMPT_NONE` depend on `ARCH_NO_PREEMPT`, and `PREEMPT_LAZY` /
  `PREEMPT_DYNAMIC` exist. The entry should state today's models.
- Not claimed: tasklet deprecation. No in-tree text states it, so we do not
  assert it.

Usage spread (files / books, translations excluded): *interrupt context*
43/22, *process context* 31/17, *atomic context* 22/12, *softirq* 55/20,
*tasklet* 18/12, *preemption* 75/19. None of those pages can link to a
definition today.

Proposed sequence (each a separate patch to linux-doc, owner
DOCUMENTATION): (a) correct the two stale entries; (b) convert the list to
`.. glossary::` with no wording change; (c) only if (b) is accepted, add
`:term:` links from a handful of high-traffic pages, one subsystem per patch.
Terms already owned elsewhere (`CRC`, `SPI`, `DSP`, `FPGA`, `device driver` in
the media and amdgpu glossaries) must not be redefined.

Process vocabulary (*merge window*, *rc1*, *linux-next*, *stable*,
*mainline*) is explained in `process/2.Process.rst`; it lacks link targets,
not definitions. Adding labels there is a smaller change than a new
glossary.

### 5. Sibling pages with identical titles that describe different things

- `PCI/endpoint/pci-ntb-howto.rst` and `pci-vntb-howto.rst` are both titled
  "PCI Non-Transparent Bridge (NTB) Endpoint Function (EPF) User Guide"; the
  second documents `pci-epf-vntb` (virtual NTB). Readers in the toctree cannot
  tell them apart. Owner: PCI ENDPOINT SUBSYSTEM.
- `tools/kabi_helpers.rst` and `tools/kdoc_ancillary.rst` are both "Ancillary
  classes" (ABI parser vs kernel-doc). Owner: DOCUMENTATION.

### 6. Two documents on path lookup

`filesystems/path-lookup.txt` (unrendered, 3k words) sits beside
`filesystems/path-lookup.rst`, and both are cited from `fs/namei.c` /
`fs/dcache.c`. Whether the `.txt` is still accurate is a VFS maintainer
question. Raise it as a question; do not send a patch.

## Deliberately not proposed

- De-duplicating per-driver boilerplate (hwmon alarms, Intel autoneg text):
  each page is read alone and owned separately.
- Splitting `kvm/api.rst`, `cgroup-v2.rst`, `ftrace.rst`: one job each
  (reference).
- Converting remaining `.txt` files (`RCU/RTFP.txt`, `spkguide.txt`, …):
  churn without reader benefit unless the owner asks.
- A kernel-wide acronym glossary (CPU, API, DMA, USB, PCI): general
  computing knowledge; out of the glossary bar.
