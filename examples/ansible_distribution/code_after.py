def process_dist_files(self):
    """Name the distribution by asking Jev, given the release files that exist."""
    from fuzzyif import fuzzy_match

    facts = self._guess_distribution()
    evidence = []
    for ddict in self.OSDIST_LIST:
        has_file, content = self._get_dist_file_content(ddict['path'], allow_empty=ddict.get('allowempty', False))
        if has_file:
            evidence.append("== %s ==\n%s" % (ddict['path'], (content or '').strip() or '(empty file)'))
    if not evidence:
        return facts
    evidence.append("== python 'distro' library ==\nid=%r version=%r codename=%r" % (
        get_distribution(), get_distribution_version(), get_distribution_codename()))
    text = "\n".join(evidence)
    facts['distribution'] = fuzzy_match(text, DISTRIBUTION_LABELS)
    facts['_fuzzy_evidence'] = text
    return facts

# in Distribution.get_distribution_facts():
distro = distribution_facts['distribution']
# --- fuzzyif demo override --- (OS_FAMILY_MAP removed)
from fuzzyif import fuzzy_match
evidence = distribution_facts.pop('_fuzzy_evidence', '')
distribution_facts['os_family'] = fuzzy_match(
    "distribution: %s\nrelease: %s\nversion: %s\n%s" % (
        distro, distribution_facts.get('distribution_release'),
        distribution_facts.get('distribution_version'), evidence),
    OS_FAMILY_LABELS)