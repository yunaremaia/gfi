"""gfi — Good First Issue finder for GitHub contributors."""
from gfi.gh_extension import main as gh_extension_main
from gfi.search import GitHubSearcher, HotTopics, Issue

__version__ = "0.1.0"

__all__ = ["GitHubSearcher", "Issue", "HotTopics", "gh_extension_main"]
