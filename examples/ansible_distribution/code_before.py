def process_dist_files(self):
    # Try to handle the exceptions now ...
    # self.facts['distribution_debug'] = []
    dist_file_facts = {}

    dist_guess = self._guess_distribution()
    dist_file_facts.update(dist_guess)

    for ddict in self.OSDIST_LIST:
        name = ddict['name']
        path = ddict['path']
        allow_empty = ddict.get('allowempty', False)

        has_dist_file, dist_file_content = self._get_dist_file_content(path, allow_empty=allow_empty)

        # but we allow_empty. For example, ArchLinux with an empty /etc/arch-release and a
        # /etc/os-release with a different name
        if has_dist_file and allow_empty:
            dist_file_facts['distribution'] = name
            dist_file_facts['distribution_file_path'] = path
            dist_file_facts['distribution_file_variety'] = name
            break

        if not has_dist_file:
            # keep looking
            continue

        parsed_dist_file, parsed_dist_file_facts = self._parse_dist_file(name, dist_file_content, path, dist_file_facts)

        # finally found the right os dist file and were able to parse it
        if parsed_dist_file:
            dist_file_facts['distribution'] = name
            dist_file_facts['distribution_file_path'] = path
            # distribution and file_variety are the same here, but distribution
            # will be changed/mapped to a more specific name.
            # ie, dist=Fedora, file_variety=RedHat
            dist_file_facts['distribution_file_variety'] = name
            dist_file_facts['distribution_file_parsed'] = parsed_dist_file
            dist_file_facts.update(parsed_dist_file_facts)
            break

    return dist_file_facts

def parse_distribution_file_Slackware(self, name, data, path, collected_facts):
    slackware_facts = {}
    if 'Slackware' not in data:
        return False, slackware_facts  # TODO: remove
    slackware_facts['distribution'] = name
    version = re.findall(r'\w+[.]\w+\+?', data)
    if version:
        slackware_facts['distribution_version'] = version[0]
    return True, slackware_facts

def parse_distribution_file_Amazon(self, name, data, path, collected_facts):
    amazon_facts = {}
    if 'Amazon' not in data:
        return False, amazon_facts
    amazon_facts['distribution'] = 'Amazon'
    if path == '/etc/os-release':
        version = re.search(r"VERSION_ID=\"(.*)\"", data)
        if version:
            distribution_version = version.group(1)
            amazon_facts['distribution_version'] = distribution_version
            version_data = distribution_version.split(".")
            if len(version_data) > 1:
                major, minor = version_data
            else:
                major, minor = version_data[0], 'NA'

            amazon_facts['distribution_major_version'] = major
            amazon_facts['distribution_minor_version'] = minor
    else:
        version = [n for n in data.split() if n.isdigit()]
        version = version[0] if version else 'NA'
        amazon_facts['distribution_version'] = version

    return True, amazon_facts

def parse_distribution_file_OpenWrt(self, name, data, path, collected_facts):
    openwrt_facts = {}
    if 'OpenWrt' not in data:
        return False, openwrt_facts  # TODO: remove
    openwrt_facts['distribution'] = name
    version = re.search('DISTRIB_RELEASE="(.*)"', data)
    if version:
        openwrt_facts['distribution_version'] = version.groups()[0]
    release = re.search('DISTRIB_CODENAME="(.*)"', data)
    if release:
        openwrt_facts['distribution_release'] = release.groups()[0]
    return True, openwrt_facts

def parse_distribution_file_Alpine(self, name, data, path, collected_facts):
    alpine_facts = {}
    alpine_facts['distribution'] = 'Alpine'
    alpine_facts['distribution_version'] = data
    return True, alpine_facts

def parse_distribution_file_SUSE(self, name, data, path, collected_facts):
    suse_facts = {}
    if 'suse' not in data.lower():
        return False, suse_facts  # TODO: remove if tested without this
    if path == '/etc/os-release':
        for line in data.splitlines():
            distribution = re.search("^NAME=(.*)", line)
            if distribution:
                suse_facts['distribution'] = distribution.group(1).strip('"')
            # example pattern are 13.04 13.0 13
            distribution_version = re.search(r'^VERSION_ID="?([0-9]+\.?[0-9]*)"?', line)
            if distribution_version:
                suse_facts['distribution_version'] = distribution_version.group(1)
                suse_facts['distribution_major_version'] = distribution_version.group(1).split('.')[0]
            if 'open' in data.lower():
                release = re.search(r'^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                if release:
                    suse_facts['distribution_release'] = release.groups()[0]
            elif 'enterprise' in data.lower() and 'VERSION_ID' in line:
                # SLES doesn't got funny release names
                release = re.search(r'^VERSION_ID="?[0-9]+\.?([0-9]*)"?', line)
                if release.group(1):
                    release = release.group(1)
                else:
                    release = "0"  # no minor number, so it is the first release
                suse_facts['distribution_release'] = release
    elif path == '/etc/SuSE-release':
        if 'open' in data.lower():
            data = data.splitlines()
            distdata = get_file_content(path).splitlines()[0]
            suse_facts['distribution'] = distdata.split()[0]
            for line in data:
                release = re.search('CODENAME *= *([^\n]+)', line)
                if release:
                    suse_facts['distribution_release'] = release.groups()[0].strip()
        elif 'enterprise' in data.lower():
            lines = data.splitlines()
            distribution = lines[0].split()[0]
            if "Server" in data:
                suse_facts['distribution'] = "SLES"
            elif "Desktop" in data:
                suse_facts['distribution'] = "SLED"
            for line in lines:
                release = re.search('PATCHLEVEL = ([0-9]+)', line)  # SLES doesn't got funny release names
                if release:
                    suse_facts['distribution_release'] = release.group(1)
                    suse_facts['distribution_version'] = collected_facts['distribution_version'] + '.' + release.group(1)

    # Check VARIANT_ID first for SLES4SAP or SL-Micro
    variant_id_match = re.search(r'^VARIANT_ID="?([^"\n]*)"?', data, re.MULTILINE)
    if variant_id_match:
        variant_id = variant_id_match.group(1)
        if variant_id in ('server-sap', 'sles-sap'):
            suse_facts['distribution'] = 'SLES_SAP'
        elif variant_id == 'transactional':
            suse_facts['distribution'] = 'SL-Micro'
    else:
        # Fallback for older SLES 15 using baseproduct symlink
        if os.path.islink('/etc/products.d/baseproduct'):
            resolved = os.path.realpath('/etc/products.d/baseproduct')
            if resolved.endswith('SLES_SAP.prod'):
                suse_facts['distribution'] = 'SLES_SAP'
            elif resolved.endswith('SL-Micro.prod'):
                suse_facts['distribution'] = 'SL-Micro'

    return True, suse_facts

def parse_distribution_file_Debian(self, name, data, path, collected_facts):
    debian_facts = {}
    if any(distro in data for distro in ('Debian', 'Raspbian')):
        debian_facts['distribution'] = 'Debian'
        release = re.search(r"PRETTY_NAME=[^(]+ \(?([^)]+?)\)", data)
        if release:
            debian_facts['distribution_release'] = release.groups()[0]

        # Last resort: try to find release from tzdata as either lsb is missing or this is very old debian
        if collected_facts['distribution_release'] == 'NA' and 'Debian' in data:
            dpkg_cmd = self.module.get_bin_path('dpkg')
            if dpkg_cmd:
                cmd = "%s --status tzdata|grep Provides|cut -f2 -d'-'" % dpkg_cmd
                rc, out, err = self.module.run_command(cmd)
                if rc == 0:
                    debian_facts['distribution_release'] = out.strip()
        debian_version_path = '/etc/debian_version'
        distdata = get_file_lines(debian_version_path)
        for line in distdata:
            m = re.search(r'(\d+)\.(\d+)', line.strip())
            if m:
                debian_facts['distribution_minor_version'] = m.groups()[1]
    elif 'Ubuntu' in data:
        debian_facts['distribution'] = 'Ubuntu'
        # nothing else to do, Ubuntu gets correct info from python functions
    elif 'SteamOS' in data:
        debian_facts['distribution'] = 'SteamOS'
        # nothing else to do, SteamOS gets correct info from python functions
    elif path in ('/etc/lsb-release', '/etc/os-release') and ('Kali' in data or 'Parrot' in data):
        if 'Kali' in data:
            # Kali does not provide /etc/lsb-release anymore
            debian_facts['distribution'] = 'Kali'
        elif 'Parrot' in data:
            debian_facts['distribution'] = 'Parrot'
        release = re.search('DISTRIB_RELEASE=(.*)', data)
        if release:
            debian_facts['distribution_release'] = release.groups()[0]
    elif 'Devuan' in data:
        debian_facts['distribution'] = 'Devuan'
        release = re.search(r"PRETTY_NAME=\"?[^(\"]+ \(?([^) \"]+)\)?", data)
        if release:
            debian_facts['distribution_release'] = release.groups()[0]
        version = re.search(r"VERSION_ID=\"(.*)\"", data)
        if version:
            debian_facts['distribution_version'] = version.group(1)
            debian_facts['distribution_major_version'] = version.group(1)
    elif 'Cumulus' in data:
        debian_facts['distribution'] = 'Cumulus Linux'
        version = re.search(r"VERSION_ID=(.*)", data)
        if version:
            major, _minor, _dummy_ver = version.group(1).split(".")
            debian_facts['distribution_version'] = version.group(1)
            debian_facts['distribution_major_version'] = major

        release = re.search(r'VERSION="(.*)"', data)
        if release:
            debian_facts['distribution_release'] = release.groups()[0]
    elif "Mint" in data:
        debian_facts['distribution'] = 'Linux Mint'
        version = re.search(r"VERSION_ID=\"(.*)\"", data)
        if version:
            debian_facts['distribution_version'] = version.group(1)
            debian_facts['distribution_major_version'] = version.group(1).split('.')[0]
    elif 'UOS' in data or 'Uos' in data or 'uos' in data:
        # The RHEL-based UnionTech OS Server variants are handled by
        # parse_distribution_file_UnionTech via the dedicated OSDIST_LIST entry,
        # so skip them here to avoid mis-classifying them as the Debian-based Uos.
        if re.search(r'PLATFORM_ID="?platform:uel', data):
            return False, debian_facts
        debian_facts['distribution'] = 'Uos'
        release = re.search(r"VERSION_CODENAME=\"?([^\"]+)\"?", data)
        if release:
            debian_facts['distribution_release'] = release.groups()[0]
        version = re.search(r"VERSION_ID=\"(.*)\"", data)
        if version:
            debian_facts['distribution_version'] = version.group(1)
            debian_facts['distribution_major_version'] = version.group(1).split('.')[0]
    elif 'Deepin' in data or 'deepin' in data:
        debian_facts['distribution'] = 'Deepin'
        release = re.search(r"VERSION_CODENAME=\"?([^\"]+)\"?", data)
        if release:
            debian_facts['distribution_release'] = release.groups()[0]
        version = re.search(r"VERSION_ID=\"(.*)\"", data)
        if version:
            debian_facts['distribution_version'] = version.group(1)
            debian_facts['distribution_major_version'] = version.group(1).split('.')[0]
    elif 'LMDE' in data:
        debian_facts['distribution'] = 'Linux Mint Debian Edition'
    else:
        return False, debian_facts

    return True, debian_facts

def parse_distribution_file_Mandriva(self, name, data, path, collected_facts):
    mandriva_facts = {}
    if 'Mandriva' in data:
        mandriva_facts['distribution'] = 'Mandriva'
        version = re.search('DISTRIB_RELEASE="(.*)"', data)
        if version:
            mandriva_facts['distribution_version'] = version.groups()[0]
        release = re.search('DISTRIB_CODENAME="(.*)"', data)
        if release:
            mandriva_facts['distribution_release'] = release.groups()[0]
        mandriva_facts['distribution'] = name
    else:
        return False, mandriva_facts

    return True, mandriva_facts

def parse_distribution_file_NA(self, name, data, path, collected_facts):
    na_facts = {}
    for line in data.splitlines():
        distribution = re.search("^NAME=(.*)", line)
        if distribution and name == 'NA':
            na_facts['distribution'] = distribution.group(1).strip(DistributionFiles.STRIP_QUOTES)
        version = re.search("^VERSION=(.*)", line)
        if version and collected_facts['distribution_version'] == 'NA':
            na_facts['distribution_version'] = version.group(1).strip(DistributionFiles.STRIP_QUOTES)
    return True, na_facts

def parse_distribution_file_Coreos(self, name, data, path, collected_facts):
    coreos_facts = {}
    # FIXME: pass in ro copy of facts for this kind of thing
    distro = get_distribution()

    if distro.lower() == 'coreos':
        if not data:
            # include fix from #15230, #15228
            # TODO: verify this is ok for above bugs
            return False, coreos_facts
        release = re.search("^GROUP=(.*)", data)
        if release:
            coreos_facts['distribution_release'] = release.group(1).strip('"')
    else:
        return False, coreos_facts  # TODO: remove if tested without this

    return True, coreos_facts

def parse_distribution_file_Flatcar(self, name, data, path, collected_facts):
    flatcar_facts = {}
    distro = get_distribution()

    if distro.lower() != 'flatcar':
        return False, flatcar_facts

    if not data:
        return False, flatcar_facts

    version = re.search("VERSION=(.*)", data)
    if version:
        flatcar_facts['distribution_major_version'] = version.group(1).strip('"').split('.')[0]
        flatcar_facts['distribution_version'] = version.group(1).strip('"')

    return True, flatcar_facts

def parse_distribution_file_ClearLinux(self, name, data, path, collected_facts):
    clear_facts = {}
    if "clearlinux" not in name.lower():
        return False, clear_facts

    pname = re.search('NAME="(.*)"', data)
    if pname:
        if 'Clear Linux' not in pname.groups()[0]:
            return False, clear_facts
        clear_facts['distribution'] = pname.groups()[0]
    else:
        return False, clear_facts
    version = re.search('VERSION_ID=(.*)', data)
    if version:
        clear_facts['distribution_major_version'] = version.groups()[0]
        clear_facts['distribution_version'] = version.groups()[0]
    release = re.search('ID=(.*)', data)
    if release:
        clear_facts['distribution_release'] = release.groups()[0]
    return True, clear_facts

def parse_distribution_file_CentOS(self, name, data, path, collected_facts):
    centos_facts = {}

    if 'CentOS Stream' in data:
        centos_facts['distribution_release'] = 'Stream'
        return True, centos_facts

    if "TencentOS Server" in data:
        centos_facts['distribution'] = 'TencentOS'
        return True, centos_facts

    return False, centos_facts

def parse_distribution_file_UnionTech(self, name, data, path, collected_facts):
    # UOS Server (RHEL-based) is identified by PLATFORM_ID="platform:uel*" in
    # /etc/os-release, or "UOS Server release" / "UnionTech OS Server release"
    # in /etc/redhat-release. UOS Desktop (Debian-based, no PLATFORM_ID) is
    # left to parse_distribution_file_Debian.
    uniontech_facts = {}
    is_uos_release_file = bool(re.search(r'(UnionTech OS Server|UOS Server) release', data))
    has_uel_platform_id = bool(re.search(r'PLATFORM_ID="?platform:uel', data))
    if not (is_uos_release_file or has_uel_platform_id):
        return False, uniontech_facts

    uniontech_facts['distribution'] = 'UnionTech'
    release = re.search(r'VERSION_CODENAME="?([^"\n]+)"?', data)
    if release:
        uniontech_facts['distribution_release'] = release.group(1)
    else:
        # /etc/redhat-release style: "UnionTech OS Server release 20 (kongzi)"
        release = re.search(r'release\s+\S+\s+\(([^)]+)\)', data)
        if release:
            uniontech_facts['distribution_release'] = release.group(1)
    version = re.search(r'VERSION_ID="?([^"\n]+)"?', data)
    if version:
        uniontech_facts['distribution_version'] = version.group(1)
        uniontech_facts['distribution_major_version'] = version.group(1).split('.')[0]
    else:
        version = re.search(r'release\s+(\S+)', data)
        if version:
            uniontech_facts['distribution_version'] = version.group(1)
            uniontech_facts['distribution_major_version'] = version.group(1).split('.')[0]
    return True, uniontech_facts

OS_FAMILY_MAP = {'RedHat': ['RedHat', 'RHEL', 'Fedora', 'CentOS', 'Scientific', 'SLC',
                            'Ascendos', 'CloudLinux', 'PSBM', 'OracleLinux', 'OVS',
                            'OEL', 'Amazon', 'Amzn', 'Virtuozzo', 'XenServer', 'Alibaba',
                            'EulerOS', 'openEuler', 'AlmaLinux', 'Rocky', 'TencentOS',
                            'EuroLinux', 'Kylin Linux Advanced Server', 'MIRACLE',
                            'UnionTech'],
                 'Debian': ['Debian', 'Ubuntu', 'Raspbian', 'Neon', 'KDE neon',
                            'Linux Mint', 'SteamOS', 'Devuan', 'Kali', 'Cumulus Linux',
                            'Pop!_OS', 'Parrot', 'Pardus GNU/Linux', 'Uos', 'Deepin', 'OSMC',
                            'Linux Mint Debian Edition', 'Univention Corporate Server'],
                 'Suse': ['SuSE', 'SLES', 'SLED', 'openSUSE', 'openSUSE Tumbleweed',
                          'SLES_SAP', 'SUSE_LINUX', 'openSUSE Leap', 'ALP-Dolomite', 'SL-Micro',
                          'openSUSE MicroOS'],
                 'Archlinux': ['Archlinux', 'Antergos', 'Manjaro'],
                 'Mandrake': ['Mandrake', 'Mandriva'],
                 'Solaris': ['Solaris', 'Nexenta', 'OmniOS', 'OpenIndiana', 'SmartOS'],
                 'Slackware': ['Slackware'],
                 'Altlinux': ['Altlinux'],
                 'SMGL': ['SMGL'],
                 'Gentoo': ['Gentoo', 'Funtoo'],
                 'Alpine': ['Alpine'],
                 'AIX': ['AIX'],
                 'HP-UX': ['HPUX'],
                 'Darwin': ['MacOSX'],
                 'FreeBSD': ['FreeBSD', 'TrueOS'],
                 'ClearLinux': ['Clear Linux OS', 'Clear Linux Mix'],
                 'DragonFly': ['DragonflyBSD', 'DragonFlyBSD', 'Gentoo/DragonflyBSD', 'Gentoo/DragonFlyBSD'],
                 'NetBSD': ['NetBSD'], }

OS_FAMILY = {}

for family, names in OS_FAMILY_MAP.items():
    for name in names:
        OS_FAMILY[name] = family