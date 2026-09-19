"""Replace Ansible's distribution-detection if/elif pile with two fuzzy_match calls.

Target: lib/ansible/module_utils/facts/system/distribution.py

Removed:
  * DistributionFiles.process_dist_files - walks OSDIST_LIST, SEARCH_STRING, OS_RELEASE_ALIAS
    and dispatches to 13 parse_distribution_file_* methods (~350 lines, 100+ if/elif)
  * Distribution.OS_FAMILY_MAP - hand-maintained name -> family table
Added:
  * one fuzzy_match over the distribution labels Ansible already documents
  * one fuzzy_match over the OS family labels
Version / release / major version keep coming from the `distro` library baseline
(_guess_distribution), which Ansible already uses as its default.

Usage: python patch_ansible.py <ansible repo> [--restore]
"""
import ast
import shutil
import sys
from pathlib import Path

MARK = "# --- fuzzyif demo override ---"

NEW_PROCESS = '''
    def process_dist_files(self):
        """Name the distribution by asking Jev, given the release files that exist."""
        from fuzzyif import fuzzy_match

        facts = self._guess_distribution()
        evidence = []
        for ddict in self.OSDIST_LIST:
            has_file, content = self._get_dist_file_content(ddict['path'], allow_empty=ddict.get('allowempty', False))
            if has_file:
                evidence.append("== %s ==\\n%s" % (ddict['path'], (content or '').strip() or '(empty file)'))
        if not evidence:
            return facts
        evidence.append("== python 'distro' library ==\\nid=%r version=%r codename=%r" % (
            get_distribution(), get_distribution_version(), get_distribution_codename()))
        text = "\\n".join(evidence)
        facts['distribution'] = fuzzy_match(text, DISTRIBUTION_LABELS)
        facts['_fuzzy_evidence'] = text
        return facts
'''

LABELS = '''
# Labels Ansible documents on its "Conditionals" page, with the conventions its
# fixtures rely on spelled out where two labels are close.
DISTRIBUTION_LABELS = {
    'ALP-Dolomite': 'SUSE ALP Dolomite', 'AlmaLinux': 'AlmaLinux', 'Amazon': 'Amazon Linux (AMI or Amazon Linux 2/2023)',
    'Archlinux': 'Arch Linux', 'CentOS': 'CentOS (Linux or Stream)', 'Clear Linux OS': 'Intel Clear Linux OS',
    'Coreos': "Container Linux by CoreOS (os-release NAME contains 'Container Linux')",
    'CoreOS': "CoreOS proper: os-release NAME is exactly 'CoreOS' (older releases, before the 'Container Linux' rename)",
    'Cumulus Linux': 'Cumulus Linux (network switch OS)', 'Debian': 'Debian GNU/Linux', 'Deepin': 'Deepin',
    'Devuan': 'Devuan GNU+Linux', 'DragonFly': 'DragonFly BSD', 'EuroLinux': 'EuroLinux', 'Fedora': 'Fedora',
    'Flatcar': 'Flatcar Container Linux by Kinvolk', 'FreeBSD': 'FreeBSD', 'Gentoo': 'Gentoo Linux',
    'KDE neon': 'KDE neon', 'Kali': 'Kali Linux', 'Kylin Linux Advanced Server': 'Kylin Linux Advanced Server',
    'Linux Mint': 'Linux Mint (Ubuntu based)', 'Linux Mint Debian Edition': 'Linux Mint Debian Edition (LMDE)',
    'MIRACLE': 'MIRACLE LINUX', 'NetBSD': 'NetBSD', 'Nexenta': 'Nexenta / NexentaStor (illumos based)',
    'OSMC': 'OSMC (Open Source Media Center)', 'OmniOS': 'OmniOS (illumos based)', 'OpenIndiana': 'OpenIndiana (illumos based)',
    'Pardus GNU/Linux': 'Pardus GNU/Linux', 'Parrot': 'Parrot OS', 'Pop!_OS': 'Pop!_OS by System76',
    'RedHat': 'Red Hat Enterprise Linux', 'Rocky': 'Rocky Linux', 'SL-Micro': 'SUSE Linux Micro (SL Micro)',
    'SLES': 'SUSE Linux Enterprise Server, standard edition (no SAP variant)',
    'SLES_SAP': "SUSE Linux Enterprise Server for SAP Applications (os-release VARIANT_ID is 'sles-sap')",
    'SMGL': 'Source Mage GNU/Linux', 'SmartOS': 'SmartOS (illumos based)', 'Solaris': 'Oracle Solaris',
    'SteamOS': 'SteamOS', 'TencentOS': 'TencentOS Server', 'Ubuntu': 'Ubuntu',
    'UnionTech': 'UnionTech / UOS Server that ships a Red Hat style /etc/system-release or /etc/redhat-release file',
    'Uos': 'UnionTech / UOS that has only os-release and lsb-release, without a system-release or redhat-release file',
    'Univention Corporate Server': 'Univention Corporate Server (UCS)', 'Virtuozzo': 'Virtuozzo Linux',
    'openEuler': 'openEuler', 'openSUSE': 'openSUSE (classic numbered release, e.g. 13.2)',
    'openSUSE Leap': 'openSUSE Leap', 'openSUSE MicroOS': 'openSUSE MicroOS', 'openSUSE Tumbleweed': 'openSUSE Tumbleweed',
    'Alpine': 'Alpine Linux', 'Altlinux': 'ALT Linux', 'OracleLinux': 'Oracle Linux', 'Slackware': 'Slackware',
    'Mandriva': 'Mandriva / Mandrake', 'OpenWrt': 'OpenWrt', 'Raspbian': 'Raspbian', 'Scientific': 'Scientific Linux',
    'Manjaro': 'Manjaro', 'Alibaba': 'Alibaba Cloud Linux', 'OpenBSD': 'OpenBSD', 'AIX': 'IBM AIX', 'HPUX': 'HP-UX',
    'MacOSX': 'macOS',
}

OS_FAMILY_LABELS = {
    'RedHat': 'Red Hat family (RHEL, Fedora, CentOS, Rocky, Alma, Amazon, Oracle, openEuler, Kylin, UnionTech server...)',
    'Debian': 'Debian family (Debian, Ubuntu, Mint, Kali, Devuan, Pop!_OS, Raspbian, Deepin, UOS desktop, Cumulus...)',
    'Suse': 'SUSE family (SLES, openSUSE, Leap, Tumbleweed, MicroOS, ALP, SL Micro)',
    'Archlinux': 'Arch family (Arch, Manjaro, Antergos)', 'Mandrake': 'Mandrake / Mandriva family',
    'Solaris': 'Solaris / illumos family (Solaris, Nexenta, OmniOS, OpenIndiana, SmartOS)',
    'Slackware': 'Slackware', 'Altlinux': 'ALT Linux', 'SMGL': 'Source Mage', 'Gentoo': 'Gentoo family (Gentoo, Funtoo)',
    'Alpine': 'Alpine', 'AIX': 'IBM AIX', 'HP-UX': 'HP-UX', 'Darwin': 'macOS / Darwin', 'FreeBSD': 'FreeBSD family (FreeBSD, TrueOS)',
    'ClearLinux': 'Intel Clear Linux', 'DragonFly': 'DragonFly BSD', 'NetBSD': 'NetBSD', 'Flatcar': 'Flatcar Container Linux',
    'Coreos': 'Container Linux by CoreOS', 'CoreOS': 'CoreOS', 'OpenWrt': 'OpenWrt', 'OpenBSD': 'OpenBSD',
}
'''

NEW_FAMILY = '''        distro = distribution_facts['distribution']
        # --- fuzzyif demo override --- (OS_FAMILY_MAP removed)
        from fuzzyif import fuzzy_match
        evidence = distribution_facts.pop('_fuzzy_evidence', '')
        distribution_facts['os_family'] = fuzzy_match(
            "distribution: %s\\nrelease: %s\\nversion: %s\\n%s" % (
                distro, distribution_facts.get('distribution_release'),
                distribution_facts.get('distribution_version'), evidence),
            OS_FAMILY_LABELS)
'''

OLD_FAMILY = '''        distro = distribution_facts['distribution']
        # look for an os family alias for the 'distribution', if there isn't one, use 'distribution'
        distribution_facts['os_family'] = self.OS_FAMILY.get(distro, None) or distro
'''


def span(tree, cls, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name == name:
                    return fn.lineno, fn.end_lineno
    return None


def main() -> None:
    repo = Path(sys.argv[1])
    target = repo / "lib/ansible/module_utils/facts/system/distribution.py"
    backup = target.with_suffix(".py.orig")
    if "--restore" in sys.argv:
        if backup.exists():
            shutil.move(backup, target)
            print("restored")
        return
    src = target.read_text(encoding="utf-8")
    if MARK in src:
        print("already patched")
        return
    shutil.copy(target, backup)
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)

    # 1. collect line ranges to delete: process_dist_files, all parse_distribution_file_*, OS_FAMILY_MAP + OS_FAMILY loop
    delete = []
    ps = span(tree, "DistributionFiles", "process_dist_files")
    delete.append(ps)
    removed_if = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DistributionFiles":
            for fn in node.body:
                if isinstance(fn, ast.FunctionDef) and fn.name.startswith("parse_distribution_file_"):
                    delete.append((fn.lineno, fn.end_lineno))
                    removed_if += sum(1 for l in lines[fn.lineno - 1:fn.end_lineno] if l.strip().startswith(("if ", "elif ")))
        if isinstance(node, ast.ClassDef) and node.name == "Distribution":
            for st in node.body:
                if isinstance(st, ast.Assign) and any(getattr(t, "id", "") in ("OS_FAMILY_MAP", "OS_FAMILY") for t in st.targets):
                    delete.append((st.lineno, st.end_lineno))
                if isinstance(st, ast.For):
                    delete.append((st.lineno, st.end_lineno))
    removed_if += sum(1 for l in lines[ps[0] - 1:ps[1]] if l.strip().startswith(("if ", "elif ")))
    removed_lines = sum(e - s + 1 for s, e in delete)

    # 2. rebuild
    out = []
    skip = set()
    for s, e in delete:
        skip.update(range(s, e + 1))
    for i, line in enumerate(lines, 1):
        if i in skip:
            if i == ps[0]:
                out.append("    " + MARK + "\n" + NEW_PROCESS)
            continue
        out.append(line)
    new_src = "".join(out)
    assert OLD_FAMILY in new_src, "os_family block not found"
    new_src = new_src.replace(OLD_FAMILY, NEW_FAMILY)
    # labels go right before class DistributionFiles
    new_src = new_src.replace("\nclass DistributionFiles:", LABELS + "\n\nclass DistributionFiles:", 1)
    target.write_text(new_src, encoding="utf-8")
    print(f"patched: removed {removed_lines} lines ({removed_if} if/elif) from {len(delete)} blocks; added 2 fuzzy_match calls")


if __name__ == "__main__":
    main()
