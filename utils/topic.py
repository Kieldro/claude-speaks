"""Derive a branch/repo-based topic identifier for Claude session audio."""

import subprocess
from pathlib import Path


def _best_word(name: str) -> str | None:
    for prefix in ('fix-', 'feat-', 'add-', 'update-', 'refactor-', 'chore-', 'bug-', 'hotfix-'):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
            break
    words = [w for w in name.replace('_', '-').split('-') if len(w) >= 3]
    if not words:
        return None
    return max(words, key=len).capitalize()


def get_topic_identifier(cwd: str = None) -> str:
    """Return a one-word identifier from branch, repo, or folder name.

    Examples:
        claude-speaks on fix-auth  → "Auth"
        claude-speaks on master    → "Speaks"
        cwd: /home/user/my-project → "Project"
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, timeout=2, cwd=cwd
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch not in ('master', 'main', 'HEAD', 'develop'):
                if '/' in branch:
                    branch = branch.rsplit('/', 1)[-1]
                word = _best_word(branch)
                if word:
                    return word

            repo_result = subprocess.run(
                ['git', 'rev-parse', '--show-toplevel'],
                capture_output=True, text=True, timeout=2, cwd=cwd
            )
            if repo_result.returncode == 0:
                word = _best_word(Path(repo_result.stdout.strip()).name)
                if word:
                    return word
    except Exception:
        pass

    if cwd:
        word = _best_word(Path(cwd).name)
        if word:
            return word
    return "Claude"
