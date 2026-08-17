"""Fail-closed semantic target scope policy for network capabilities."""

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

from xhunter.contracts.policy import PolicyDecision
from xhunter.contracts.tool import ToolRequest

_TARGET_ARGUMENTS = ("url", "target", "host")


@dataclass(frozen=True, slots=True)
class ScopePolicyConfig:
    allowed_targets: tuple[str, ...]
    blocked_targets: tuple[str, ...] = ()
    network_capability_prefixes: tuple[str, ...] = ("network.", "browser.")


class ScopePolicy:
    def __init__(self, config: ScopePolicyConfig) -> None:
        self._config = config
        (
            self._allowed_hosts,
            self._allowed_wildcards,
            self._allowed_networks,
        ) = _parse_scope(config.allowed_targets)
        (
            self._blocked_hosts,
            self._blocked_wildcards,
            self._blocked_networks,
        ) = _parse_scope(config.blocked_targets)

    async def authorize(self, request: ToolRequest) -> PolicyDecision:
        if not request.capability.startswith(self._config.network_capability_prefixes):
            return PolicyDecision(allowed=True)

        target = _target_from(request)
        if target is None:
            return PolicyDecision(False, "network action requires an explicit target")
        if _matches(
            target,
            self._blocked_hosts,
            self._blocked_wildcards,
            self._blocked_networks,
        ):
            return PolicyDecision(False, f"target is explicitly blocked: {target}")
        if not _matches(
            target,
            self._allowed_hosts,
            self._allowed_wildcards,
            self._allowed_networks,
        ):
            return PolicyDecision(False, f"target is outside mission scope: {target}")
        return PolicyDecision(allowed=True)


def _target_from(request: ToolRequest) -> str | None:
    for name in _TARGET_ARGUMENTS:
        value = request.arguments.get(name)
        if not isinstance(value, str) or not value.strip():
            continue
        parsed = urlsplit(value if "://" in value else f"//{value}")
        host = parsed.hostname
        return host.rstrip(".").lower() if host else None
    return None


def _parse_scope(
    entries: tuple[str, ...],
) -> tuple[
    frozenset[str],
    frozenset[str],
    tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
]:
    hosts: set[str] = set()
    wildcards: set[str] = set()
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in entries:
        normalized = entry.strip().rstrip(".").lower()
        if not normalized:
            raise ValueError("scope entries must not be empty")
        if normalized.startswith("*."):
            suffix = normalized[2:]
            if not suffix or "*" in suffix:
                raise ValueError(f"invalid wildcard scope entry: {entry}")
            wildcards.add(suffix)
            continue
        if "*" in normalized:
            raise ValueError(f"invalid wildcard scope entry: {entry}")
        try:
            networks.append(ipaddress.ip_network(normalized, strict=False))
        except ValueError:
            hosts.add(normalized)
    return frozenset(hosts), frozenset(wildcards), tuple(networks)


def _matches(
    target: str,
    hosts: frozenset[str],
    wildcards: frozenset[str],
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
) -> bool:
    if target in hosts:
        return True
    if any(target.endswith(f".{suffix}") for suffix in wildcards):
        return True
    try:
        address = ipaddress.ip_address(target)
    except ValueError:
        return False
    return any(address in network for network in networks)
