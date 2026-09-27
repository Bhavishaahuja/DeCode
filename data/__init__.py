"""DeCode data layer. Public API: `from data.search import search_evidence`."""


def search_evidence(query, site=None, system=None, k=8):
    from .search import search_evidence as _s
    return _s(query, site=site, system=system, k=k)
