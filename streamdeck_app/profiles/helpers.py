"""Small action constructors to keep profile files readable."""

from __future__ import annotations

from .model import Action


def key(name: str) -> Action:
    return {"type": "key", "key": name}


def hotkey(*keys: str) -> Action:
    return {"type": "hotkey", "keys": list(keys)}


def open_target(target: str) -> Action:
    return {"type": "open", "target": target}


def launch(*command: str) -> Action:
    return {"type": "launch", "command": list(command)}
