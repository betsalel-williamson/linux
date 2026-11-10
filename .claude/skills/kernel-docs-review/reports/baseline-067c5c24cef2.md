# Baseline docs review at 067c5c24cef2

Snapshot of `Documentation/` at commit `067c5c24cef2` (around v7.4-rc2).
Tools: `scripts/rst_review.py` from this skill,
`tools/docs/documentation-file-ref-check`, and manual verification against
the source tree, then a full `make htmldocs` (Sphinx 9.2.0, kernel
`Documentation/sphinx/requirements.txt`) and a prior-work check against
linux-next, Patchwork and Bugzilla. Those results are in
[Sphinx build](#sphinx-build) and [Prior work](#prior-work) at the end and
override any finding above them.

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

## Sphinx build

Full `make htmldocs` at `067c5c24cef2`, `-j4`, 4,135 HTML
pages. **69 unique warnings/errors**, none of which overlap the findings
above (Sphinx does not see `MAINTAINERS`, C comments citing doc paths,
stale facts, or duplicate titles).

| Kind                                         | Count | Mostly from |
| -------------------------------------------- | ----: | ----------- |
| Duplicate C declaration (same symbol pulled in twice by `kernel-doc`) | 36 | `gpu/drm-kms-helpers` + `drm_panel.c`, `power/runtime_pm` |
| kernel-doc member/param undocumented or excess | 17 | `host1x.h`, `jbd2.h`, `page_pool/types.h`, amdgpu `dc.h` |
| ABI: same sysfs path defined in two files      | 4  | `sysfs-driver-hid-lenovo-go` vs `-go-s` |
| docutils inline markup                         | 3  | `power/power_supply_class.rst:211`, `ABI/testing/sysfs-class-power-rt9467`, `-rt9471` |
| docutils unknown target                        | 3  | `drivers/tty/vt/vt.c` (changed in linux-next; may be fixed) |
| other (highlighting, unparseable xref, graphviz missing) | 6 | `drm_gpusvm.c`, environment |

Most of these belong to subsystem maintainers, not linux-doc
(`doc-guide/contributing.rst` says the same). The sources of the jbd2,
host1x, page_pool, gpusvm, amdgpu, lenovo-go and power_supply warnings are
unchanged in linux-next 20261109. A build of linux-next itself was not run.

Side finding: `doc-guide/contributing.rst` still says the build "spews out
an unbelievable number of warnings". At 69 that is no longer true, and it
undersells the cleanup work that has been done. A one-paragraph update is
for the documentation maintainer to judge.

## Prior work

Checked 2026-11-10. Sources: linux-next `master` (20261109), the Patchwork
API at patchwork.kernel.org (subject search across 124 projects), and the
Bugzilla REST API. **Not checked: lore.kernel.org** (still refused by the
network policy at the time of writing). linux-doc has no project on
patchwork.kernel.org, so docs-only patches are not visible in Patchwork.
Every "nothing found" below for a docs-only file means "not visible in
Patchwork", not "no patch exists".

| Finding | In linux-next? | Existing patches | Action |
| ------- | -------------- | ---------------- | ------ |
| 1. MAINTAINERS MegaChips `F:` | not fixed | **two unapplied:** "MAINTAINERS: adjust file entry in MEGACHIPS BRIDGES" (2025-10-01, devicetree, state *new*); "MAINTAINERS: update MEGACHIPS dt-binding path to yaml" (2026-09-08, dri-devel, *new*) | **Do not send a third.** Review or reply to the newer one (a `Reviewed-by` from a human who checked it), or ask the DRM bridge maintainers which tree should take it |
| 2a. `arch/arm/xen/enlighten.c` cites `xen.txt` | not fixed | the conversion patch (2026-06-15) was *changes-requested*; `xen.yaml` is in the tree now, but the comment still cites `xen.txt` | candidate, small; send to XEN HYPERVISOR ARM |
| 2b. `mpic.c` cites `mpic.txt` | not fixed | none visible | still needs powerpc maintainers to confirm the successor binding |
| 2c. sm5703 regulator → missing mfd yaml | not fixed | none visible | binding author's call; not ours |
| 4. locking.rst glossary stale | not fixed | not visible (linux-doc not in Patchwork; lore unchecked) | **hold until lore is checked**. Context: active series replace tasklets with BH workqueues ("dmaengine: … use dmaengine BH instead of tasklets", v4 2026-11-10; "net/rds: replace tasklets with workqueue", accepted 2026-09-24). Still no in-tree statement that tasklets are deprecated |
| 5a. vNTB title | not fixed | **active series** "Documentation: PCI: endpoint: Document vNTB DMA export" (v9, 2026-11-10) edits `pci-vntb-howto.rst` | do not send separately; suggest the title fix in review of that series, or wait until it lands |
| 5b. "Ancillary classes" ×2 | not fixed | not visible | hold until lore is checked |
| 6. path-lookup.txt | present | rename attempt in 2020 ("docs: filesystems: rename path-lookup.txt file", never applied) | question for VFS maintainers, unchanged |

### New: open Bugzilla reports against in-tree docs

Bugzilla's *Documentation* product is almost all man-pages (a separate
project) plus unremoved spam; the kernel tracks in-tree docs work on the
lists. Five open bugs concern `Documentation/`:

| Bug | Report | Status in linux-next | Action |
| --- | ------ | -------------------- | ------ |
| [194593](https://bugzilla.kernel.org/show_bug.cgi?id=194593) (2017) | `/proc/<pid>/stat` times documented as "jiffies" | **still wrong:** `filesystems/proc.rst:339-342,369-370` say jiffies; `fs/proc/array.c:603-646` prints `nsec_to_clock_t()`, i.e. USER_HZ ticks; the same file says "USER_HZ" for `/proc/stat` at line 1597 | **strong candidate.** User-facing ABI doc, nine years open, internally inconsistent. Owner: PROC FILESYSTEM + DOCUMENTATION. Coordinate with the in-flight procfs-core series ("proc: let procfs own the seq_file of /proc/stat", RESEND v2 2026-11-04) |
| [217783](https://bugzilla.kernel.org/show_bug.cgi?id=217783) | `can.rst` shows `frames[0]` | fixed (`can.rst:745` has `frames[]`) | ask a Bugzilla admin to close; no patch |
| [197891](https://bugzilla.kernel.org/show_bug.cgi?id=197891) | `/proc/sys/fscache` undocumented | obsolete: no fscache sysctls remain in `fs/netfs` / `fs/fscache` | close; no patch |
| [217375](https://bugzilla.kernel.org/show_bug.cgi?id=217375) | intel_pstate in kernel-parameters | reporter says it went to the list | close |
| [214931](https://bugzilla.kernel.org/show_bug.cgi?id=214931) | comma/grammar edits to `2.Process.rst` | style only | leave (fails the value bar) |

### Revised ranking

1. `proc.rst` per-PID time units (bug 194593): verified, user-facing, no
   competing patch visible. Best first patch, once lore confirms nothing is
   pending on linux-fsdevel.
2. MegaChips `MAINTAINERS`: support an existing patch; do not write one.
3. `enlighten.c` comment path: small and clean.
4. locking.rst glossary and "Ancillary classes": after the lore check.
