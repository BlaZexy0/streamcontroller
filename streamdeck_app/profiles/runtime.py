"""Mutable profile selection and lifecycle state, separate from the service loop."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable

from .model import Profile, ProfileContext, ProfileLifecycle


class ProfileRuntime:
    def __init__(self, profiles: Iterable[Profile]) -> None:
        self.profiles = list(profiles)
        if not self.profiles:
            raise ValueError("Mindestens ein Profil ist erforderlich")
        self.lifecycles: list[ProfileLifecycle] = [
            profile.lifecycle_factory() for profile in self.profiles
        ]
        self.index = 0
        self.active_index: int | None = None
        self.candidate_index = 0
        self.candidate_since = time.monotonic()
        self.locked = False

    @property
    def profile(self) -> Profile:
        return self.profiles[self.index]

    @property
    def lifecycle(self) -> ProfileLifecycle:
        return self.lifecycles[self.index]

    def resolve(self, process_name: str) -> int:
        for index, profile in enumerate(self.profiles):
            if profile.matches(process_name):
                return index
        return next(
            index for index, profile in enumerate(self.profiles) if not profile.processes
        )

    def activate(
        self,
        index: int,
        context_for: Callable[[int], ProfileContext],
        render: Callable[[], None],
    ) -> None:
        index %= len(self.profiles)
        if self.active_index == index:
            self.index = index
            render()
            return

        if self.active_index is not None:
            old_index = self.active_index
            self.lifecycles[old_index].on_deactivate(context_for(old_index))

        self.index = index
        self.active_index = index
        render()
        self.lifecycles[index].on_activate(context_for(index))

    def observe_process(self, process_name: str, now: float, debounce: float) -> int | None:
        new_index = self.resolve(process_name)
        if new_index == self.index:
            self.candidate_index = new_index
            self.candidate_since = now
            return None
        if new_index != self.candidate_index:
            self.candidate_index = new_index
            self.candidate_since = now
            return None
        if now - self.candidate_since < debounce:
            return None
        return new_index

    def reset_candidate(self, index: int, now: float) -> None:
        self.candidate_index = index
        self.candidate_since = now

    def on_button(self, context: ProfileContext, index: int, pressed: bool) -> bool:
        return self.lifecycle.on_button(context, index, pressed)

    def on_encoder(self, context: ProfileContext, index: int, direction: str) -> bool:
        return self.lifecycle.on_encoder(context, index, direction)

    def on_tick(self, context: ProfileContext, now: float) -> None:
        self.lifecycle.on_tick(context, now)
