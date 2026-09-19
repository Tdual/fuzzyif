# Ansible: which Linux distribution is this?

Ansible's `setup` module reports `ansible_distribution` and `ansible_os_family`
for every host. The code that decides them lives in
`lib/ansible/module_utils/facts/system/distribution.py`: it walks a list of
release files (`/etc/os-release`, `/etc/redhat-release`, `/etc/lsb-release`,
`/etc/SuSE-release`, ...), matches search strings, and dispatches to thirteen
`parse_distribution_file_*` methods, each a ladder of `if`/`elif` on the file
contents. A hand-maintained `OS_FAMILY_MAP` then maps the name to a family.

This example deletes that pile and asks two questions instead.

## The change

| | before | after |
|---|---|---|
| `distribution.py` | 786 lines | 450 lines |
| removed | `process_dist_files`, 13 `parse_distribution_file_*` methods, `OS_FAMILY_MAP` (402 lines, 84 `if`/`elif`) | |
| added | | two `fuzzy_match` calls plus two label dictionaries (~60 lines) |

```python
def process_dist_files(self):
    facts = self._guess_distribution()            # version / codename from the `distro` library, as before
    evidence = []
    for ddict in self.OSDIST_LIST:                # the same file list Ansible already has
        has_file, content = self._get_dist_file_content(ddict['path'], allow_empty=ddict.get('allowempty', False))
        if has_file:
            evidence.append("== %s ==\n%s" % (ddict['path'], (content or '').strip() or '(empty file)'))
    if not evidence:
        return facts
    evidence.append("== python 'distro' library ==\nid=%r version=%r codename=%r" % (...))
    facts['distribution'] = fuzzy_match("\n".join(evidence), DISTRIBUTION_LABELS)
    return facts
```

```python
distribution_facts['os_family'] = fuzzy_match(evidence_with_name, OS_FAMILY_LABELS)
```

`DISTRIBUTION_LABELS` is the list of names Ansible documents on its
*Conditionals* page, with a one-line description each. Where Ansible keeps two
labels for one operating system (`CoreOS` vs `Coreos`, `SLES` vs `SLES_SAP`,
`UnionTech` vs `Uos`) the description spells out Ansible's convention.
`patch_ansible.py` applies and reverts the edit.

## Ansible's own tests

`test/units/module_utils/facts/system/distribution/test_distribution_version.py`
feeds 90 recorded fixtures (real `/etc/*-release` contents from 52 distributions)
through the collector and compares every reported key.

| | before | after |
|---|---|---|
| fixtures | 90 | 90 |
| passed | 90 | 65 |
| failed | 0 | 25 |
| wall time | 0.1 s | 47 s (180 Jev calls, no cache) |

What the two questions were asked to decide:

| key | agreement |
|---|---|
| `distribution` (which distro) | 90 / 90 |
| `os_family` | 89 / 90 |

The one `os_family` miss is `Uos 20`: Ansible labels the same UnionTech OS as
`Uos` (Debian family) or `UnionTech` (RedHat family) depending on which release
files are present. The judge picked the other one.

What the 25 failing fixtures are actually about:

| failing key | count | what Ansible's parsers were doing |
|---|---|---|
| `distribution_release` | 21 | SUSE: put the service-pack number in `release` (`15-SP6` → `6`); openSUSE Leap: the minor digit (`15.1` → `1`); Clear Linux: the literal `clear-linux-os`; CentOS: `Stream`; Devuan: the codename from `/etc/devuan_version`; Cumulus: the whole `DISTRIB_DESCRIPTION` |
| `distribution_minor_version` | 3 | Debian and Amazon parsers add a key the `distro` baseline does not |
| `distribution_version` | 1 | OSMC: `March 2022` read from a custom file |
| `os_family` | 1 | the `Uos` / `UnionTech` label pair above |

None of these is a judgement. They are string-extraction conventions, and the
fuzzy version deliberately does not try to reproduce them: it keeps whatever the
`distro` library reports for version and codename. That is the boundary this
example is meant to show. **fuzzy-if replaces the `if` ladder that decides what
something is. It does not replace the code that cuts a substring out of a file.**

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
