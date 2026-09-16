"""Detect which provider CLI tools are installed on this machine.

Detection is filesystem-only (no subprocess is spawned): each provider's
executable is looked up on ``PATH`` and then in the well-known install
directories used by the native installers and by npm on Windows. Results are
cached for the process lifetime; call ``detect_installed_clis(force=True)``
to rescan after installing a CLI.
"""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .base_provider import BaseLLMProvider, LLMProviderRegistry


@dataclass(frozen=True)
class CliStatus:
    """Where (and whether) one provider's CLI was found."""

    provider_name: str
    executable: str
    path: str = ""

    @property
    def installed(self) -> bool:
        return bool(self.path)


_CACHE: Dict[str, CliStatus] = {}


def _fallback_dirs() -> List[Path]:
    """Directories the native installers and npm use when not on PATH."""
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())
    dirs = [
        home / ".local" / "bin",
        home / ".grok" / "bin",
        home / ".opencode" / "bin",
        home / ".codex" / "bin",
        home / ".claude" / "bin",
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(Path(appdata) / "npm")
    return dirs


def _candidate_names(executable: str) -> List[str]:
    if sys.platform == "win32":
        return [f"{executable}.exe", f"{executable}.cmd", f"{executable}.bat"]
    return [executable]


def locate_cli(executable: str) -> Optional[str]:
    """Return the resolved path of ``executable`` or ``None`` when absent."""
    found = shutil.which(executable)
    if found:
        return found
    for directory in _fallback_dirs():
        for name in _candidate_names(executable):
            candidate = directory / name
            if candidate.is_file():
                return str(candidate)
    return None


def detect_installed_clis(force: bool = False) -> Dict[str, CliStatus]:
    """Return ``{provider_name: CliStatus}`` for every registered provider."""
    if _CACHE and not force:
        return dict(_CACHE)
    _CACHE.clear()
    for provider in LLMProviderRegistry.all():
        executable = provider.cli_executable
        _CACHE[provider.name] = CliStatus(
            provider_name=provider.name,
            executable=executable,
            path=locate_cli(executable) or "",
        )
    return dict(_CACHE)


def is_provider_installed(provider: BaseLLMProvider) -> bool:
    status = detect_installed_clis().get(provider.name)
    return bool(status and status.installed)


def installed_providers() -> List[BaseLLMProvider]:
    """Registered providers whose CLI was found, in registry order."""
    return [provider for provider in LLMProviderRegistry.all() if is_provider_installed(provider)]


def missing_providers() -> List[BaseLLMProvider]:
    """Registered providers whose CLI was not found, in registry order."""
    return [provider for provider in LLMProviderRegistry.all() if not is_provider_installed(provider)]
