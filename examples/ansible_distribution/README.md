# Ansible: which Linux distribution is this?

Ansible's `setup` module reports `ansible_distribution` and `ansible_os_family`
for every host. The code that decides them lives in
`lib/ansible/module_utils/facts/system/distribution.py`: it walks a list of
release files (`/etc/os-release`, `/etc/redhat-release`, `/etc/lsb-release`,
`/etc/SuSE-release`, ...), matches search strings, and dispatches to thirteen
`parse_distribution_file_*` methods, each a ladder of `if`/`elif` on the file
contents. A hand-maintained `OS_FAMILY_MAP` then maps the name to a family.

This example deletes that pile and asks two questions instead.

## Before

![Before](../../docs/images/ansible_before.png)

## After

![After](../../docs/images/ansible_after.png)

```python
distribution_facts['os_family'] = fuzzy_match(evidence_with_name, OS_FAMILY_LABELS)
```

`DISTRIBUTION_LABELS` lists the names Ansible documents on its *Conditionals*
page with a one-line description each. Where Ansible keeps two labels for one
operating system (`CoreOS` vs `Coreos`, `SLES` vs `SLES_SAP`, `UnionTech` vs
`Uos`) the description spells out Ansible's convention. `patch_ansible.py`
applies and reverts the edit.

## Size

| | Before | After |
|---|---|---|
| `distribution.py` | 786 lines | 450 lines |
| `if` / `elif` in the detection code | 84 | 0 |
| parser methods | 13 | 0 |
| name → family table | 70 entries | none |
| lines added | | 2 `fuzzy_match` calls, 2 label dictionaries (about 60 lines) |

## Ansible's own tests

`test/units/module_utils/facts/system/distribution/test_distribution_version.py`
feeds 90 recorded fixtures (real `/etc/*-release` contents from 52 distributions)
through the collector and compares every reported key.

| Result key | Agreement |
|---|---|
| `distribution` | 90 / 90 |
| `os_family` | 87 / 88 |
| `distribution_version` | 88 / 90 |
| `distribution_major_version` | 84 / 84 |
| `distribution_cpe_name` | 20 / 20 |
| `distribution_release` | 68 / 88 |
| `distribution_minor_version` | 0 / 3 |

| Fixtures | Before | After |
|---|---|---|
| all keys match | 90 | 65 |
| any key differs | 0 | 25 |
| wall time | 0.1 s | 47 s (180 Jev calls, cold cache) |

## What the 25 differences are

26 key mismatches across 25 fixtures.

| Key | Count | Convention the deleted parser implemented |
|---|---|---|
| `distribution_release` | 20 | SUSE: the service-pack number (`15-SP6` → `6`); openSUSE Leap: the minor digit (`15.1` → `1`); Clear Linux: the literal `clear-linux-os`; CentOS: `Stream`; Devuan: the codename from `/etc/devuan_version`; Cumulus: the whole `DISTRIB_DESCRIPTION` |
| `distribution_minor_version` | 3 | Debian and Amazon parsers add a key the `distro` baseline does not |
| `distribution_version` | 2 | OSMC: `March 2022` read from a custom file; SLES 11.3: patch level from `/etc/SuSE-release` |
| `os_family` | 1 | Ansible labels the same UnionTech OS `Uos` (Debian family) or `UnionTech` (RedHat family) depending on which release files exist; the judge picked the other one |

None of these is a judgement. They are string-extraction conventions, and the
fuzzy version deliberately does not reproduce them: it keeps whatever the
`distro` library reports for version and codename. **fuzzy-if replaces the `if`
ladder that decides what something is. It does not replace the code that cuts a
substring out of a file.**

## Reproduce

```bash
git clone --depth 1 https://github.com/ansible/ansible
cd ansible && python3.13 -m venv .venv && .venv/bin/pip install -e . pytest pytest-mock fuzzyif
python /path/to/fuzzyif/examples/ansible_distribution/patch_ansible.py .
.venv/bin/pytest -q test/units/module_utils/facts/system/distribution/test_distribution_version.py
python /path/to/fuzzyif/examples/ansible_distribution/patch_ansible.py . --restore
```

Ansible `main` (2.23.0.dev0) requires Python 3.13; on 3.12 add
`--ignore-requires-python` to the install command, which is what the numbers
above were produced with.

The images were rendered from the deleted and added code with Pygments; the
sources are `code_before.py` and `code_after.py` next to this file.
