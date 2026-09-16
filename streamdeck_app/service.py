"""Context-aware SOOMFON controller service."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from .core.actions import execute
from .core.audio import AudioController, AudioUnavailableError, WindowsAudioController
from .core.device import Deck, DeckConnectionError, decode_event
from .core.foreground import ForegroundWindow, current_window
from .core.interfaces import DeckInterface
from .market import MarketDataWorker, MarketResult, YahooMarketDataProvider
from .profiles import ALL_PROFILES, Profile, ProfileContext, ProfileLifecycle
from .profiles.model import Action
from .profiles.reload import ProfileReloader
from .profiles.runtime import ProfileRuntime
from .screens import (
    DisplayContent,
    DisplayController,
    IdleAnimation,
    device_overlay,
    message_overlay,
    market_tile,
    profile_tile,
    volume_overlay,
)
from .settings import Settings, load_settings, validate_action


ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("streamdeck")


class ControllerService:
    def __init__(
        self,
        config_path: Path,
        *,
        deck_factory: Callable[[], DeckInterface] = Deck,
        foreground_provider: Callable[[], ForegroundWindow] = current_window,
        dev_reload: bool = False,
        audio_controller: AudioController | None = None,
        market_worker: MarketDataWorker | None = None,
    ) -> None:
        self.settings: Settings = load_settings(config_path)
        self.deck_factory = deck_factory
        self.foreground_provider = foreground_provider
        self.audio_controller = audio_controller or WindowsAudioController()
        self.market_worker = market_worker
        if self.settings.market_enabled and self.market_worker is None:
            self.market_worker = MarketDataWorker(
                YahooMarketDataProvider(),
                self.settings.market_watchlist,
                refresh_seconds=self.settings.market_refresh_seconds,
                closed_refresh_seconds=self.settings.market_closed_refresh_seconds,
            )
        self.profile_runtime = ProfileRuntime(ALL_PROFILES)
        self.profile_reloader = ProfileReloader() if dev_reload else None
        self.display = DisplayController()
        self.validate_profiles(self.profiles)
        self.last_input = time.monotonic()
        self.last_window_poll = 0.0
        self.idle = False
        self.animation: IdleAnimation | None = None
        self.animation_frame = 0
        self.next_animation_frame = 0.0
        self.screensaver_hold_started_at: float | None = None
        self.screensaver_hold_triggered = False
        self.audio_device_hold_started_at: float | None = None
        self.audio_device_hold_triggered = False
        self.market_revision = -1

    @staticmethod
    def validate_profiles(profiles: list[Profile] | tuple[Profile, ...]) -> None:
        for profile in profiles:
            for index, button in enumerate(profile.buttons):
                if button.action is not None:
                    validate_action(button.action, f"Profil {profile.name}, Taste {index + 1}")

    @property
    def profile(self) -> Profile:
        return self.profile_runtime.profile

    @property
    def profiles(self) -> list[Profile]:
        return self.profile_runtime.profiles

    @property
    def profile_lifecycles(self) -> list[ProfileLifecycle]:
        return self.profile_runtime.lifecycles

    @property
    def profile_index(self) -> int:
        return self.profile_runtime.index

    @profile_index.setter
    def profile_index(self, value: int) -> None:
        self.profile_runtime.index = value

    @property
    def candidate_profile_index(self) -> int:
        return self.profile_runtime.candidate_index

    @candidate_profile_index.setter
    def candidate_profile_index(self, value: int) -> None:
        self.profile_runtime.candidate_index = value

    @property
    def candidate_since(self) -> float:
        return self.profile_runtime.candidate_since

    @candidate_since.setter
    def candidate_since(self, value: float) -> None:
        self.profile_runtime.candidate_since = value

    @property
    def locked(self) -> bool:
        return self.profile_runtime.locked

    @locked.setter
    def locked(self, value: bool) -> None:
        self.profile_runtime.locked = value

    def resolve_profile(self, process_name: str) -> int:
        return self.profile_runtime.resolve(process_name)

    def render_profile(self, deck: DeckInterface) -> None:
        LOG.info("Profil: %s%s", self.profile.name, " [gesperrt]" if self.locked else "")
        self.display.set_base(
            [profile_tile(button, self.locked) for button in self.profile.buttons]
        )
        if not self.idle:
            self.display.render(deck)

    def render_market_tiles(self, deck: DeckInterface) -> None:
        if not self.settings.market_enabled or self.market_worker is None:
            return
        revision, results = self.market_worker.snapshot()
        current = time.time()
        for offset, item in enumerate(self.settings.market_watchlist):
            deck.set_key_image(
                3 + offset,
                market_tile(
                    item,
                    results.get(item.symbol, MarketResult()),
                    stale_seconds=self.settings.market_stale_seconds,
                    now=current,
                ),
            )
        self.market_revision = revision

    def poll_market(self, deck: DeckInterface, now: float) -> None:
        if not self.settings.market_enabled or self.market_worker is None:
            return
        revision, _ = self.market_worker.snapshot()
        if revision == self.market_revision:
            return
        self.market_revision = revision
        if self.idle:
            self.render_market_tiles(deck)

    def profile_context(self, deck: DeckInterface, index: int | None = None) -> ProfileContext:
        profile_index = self.profile_index if index is None else index
        return ProfileContext(
            deck=deck,
            profile=self.profiles[profile_index],
            run_action=lambda action: self.run_action(deck, action),
            request_render=lambda: None if self.idle else self.display.render(deck),
            set_key_image=lambda key, image: self.set_profile_key(deck, key, image),
            show_overlay=lambda images, duration: self.show_overlay(
                deck, images, duration
            ),
        )

    def set_profile_key(
        self,
        deck: DeckInterface,
        key: int,
        image: DisplayContent,
    ) -> None:
        self.display.set_base_key(key, image)
        if not self.idle:
            self.display.render(deck)

    def show_overlay(
        self,
        deck: DeckInterface,
        images: dict[int, DisplayContent],
        duration: float,
    ) -> None:
        self.display.show_overlay(
            images,
            now=time.monotonic(),
            duration=duration,
        )
        if not self.idle:
            self.display.render(deck)

    def activate_profile(self, deck: DeckInterface, index: int) -> None:
        target = index % len(self.profiles)
        if (
            self.profile_runtime.active_index is not None
            and self.profile_runtime.active_index != target
        ):
            self.display.clear_overlays()
        self.profile_runtime.activate(
            index,
            lambda profile_index: self.profile_context(deck, profile_index),
            lambda: self.render_profile(deck),
        )

    def cycle_profile(self, deck: DeckInterface, delta: int) -> None:
        self.locked = True
        self.activate_profile(deck, self.profile_index + delta)

    def internal_action(self, deck: DeckInterface, name: str) -> None:
        if name == "previous_profile":
            self.cycle_profile(deck, -1)
        elif name == "next_profile":
            self.cycle_profile(deck, 1)
        elif name == "toggle_lock":
            self.locked = not self.locked
            if not self.locked:
                window = self.foreground_provider()
                new_index = self.profile_index
                if window.process_name.lower() not in self.settings.ignored_processes:
                    new_index = self.resolve_profile(window.process_name)
                self.candidate_profile_index = new_index
                self.candidate_since = time.monotonic()
                self.activate_profile(deck, new_index)
            else:
                self.render_profile(deck)
        elif name == "system_volume_down":
            self.change_system_volume(deck, -2)
        elif name == "system_volume_up":
            self.change_system_volume(deck, 2)
        elif name == "system_volume_mute":
            self.toggle_system_mute(deck)
        elif name == "application_volume_down":
            self.change_application_volume(deck, -2)
        elif name == "application_volume_up":
            self.change_application_volume(deck, 2)
        elif name == "application_volume_mute":
            self.toggle_application_mute(deck)
        elif name == "microphone_volume_down":
            self.change_microphone_volume(deck, -2)
        elif name == "microphone_volume_up":
            self.change_microphone_volume(deck, 2)
        elif name == "microphone_volume_mute":
            self.toggle_microphone_mute(deck)
        else:
            raise ValueError(f"Unbekannte interne Aktion: {name}")

    def change_system_volume(self, deck: DeckInterface, delta: int) -> None:
        try:
            state = self.audio_controller.change_system_volume(delta)
            self.show_overlay(deck, volume_overlay(state), self.settings.audio_overlay_seconds)
        except AudioUnavailableError as exc:
            LOG.error("Audioaktion fehlgeschlagen: %s", exc)
            self.show_audio_error(deck, exc)

    def toggle_system_mute(self, deck: DeckInterface) -> None:
        try:
            state = self.audio_controller.toggle_system_mute()
            self.show_overlay(deck, volume_overlay(state), self.settings.audio_overlay_seconds)
        except AudioUnavailableError as exc:
            LOG.error("Audioaktion fehlgeschlagen: %s", exc)
            self.show_audio_error(deck, exc)

    def change_application_volume(self, deck: DeckInterface, delta: int) -> None:
        window = self.foreground_provider()
        try:
            state = self.audio_controller.change_application_volume(
                window.process_id,
                window.process_name,
                delta,
            )
            self.show_overlay(deck, volume_overlay(state), self.settings.audio_overlay_seconds)
        except AudioUnavailableError as exc:
            LOG.warning("App-Audioaktion fehlgeschlagen: %s", exc)
            self.show_audio_error(deck, exc)

    def toggle_application_mute(self, deck: DeckInterface) -> None:
        window = self.foreground_provider()
        try:
            state = self.audio_controller.toggle_application_mute(
                window.process_id,
                window.process_name,
            )
            self.show_overlay(deck, volume_overlay(state), self.settings.audio_overlay_seconds)
        except AudioUnavailableError as exc:
            LOG.warning("App-Audioaktion fehlgeschlagen: %s", exc)
            self.show_audio_error(deck, exc)

    def change_microphone_volume(self, deck: DeckInterface, delta: int) -> None:
        try:
            state = self.audio_controller.change_microphone_volume(delta)
            self.show_overlay(deck, volume_overlay(state), self.settings.audio_overlay_seconds)
        except AudioUnavailableError as exc:
            LOG.warning("Mikrofonaktion fehlgeschlagen: %s", exc)
            self.show_audio_error(deck, exc)

    def toggle_microphone_mute(self, deck: DeckInterface) -> None:
        try:
            state = self.audio_controller.toggle_microphone_mute()
            self.show_overlay(deck, volume_overlay(state), self.settings.audio_overlay_seconds)
        except AudioUnavailableError as exc:
            LOG.warning("Mikrofonaktion fehlgeschlagen: %s", exc)
            self.show_audio_error(deck, exc)

    def cycle_output_device(self, deck: DeckInterface) -> None:
        try:
            state = self.audio_controller.cycle_output_device(
                self.settings.audio_output_devices
            )
            self.show_overlay(deck, device_overlay(state), self.settings.audio_overlay_seconds)
            LOG.info("Audioausgabe gewechselt: %s", state.name)
        except AudioUnavailableError as exc:
            LOG.warning("Audiogeraetewechsel fehlgeschlagen: %s", exc)
            self.show_audio_error(deck, exc)

    def show_audio_error(self, deck: DeckInterface, error: Exception) -> None:
        detail = "SESSION" if "sitzung" in str(error).casefold() else "GERAET"
        self.show_overlay(
            deck,
            message_overlay("KEIN", "AUDIO", detail),
            self.settings.audio_overlay_seconds,
        )

    def run_action(self, deck: DeckInterface, action: Action | None) -> None:
        try:
            execute(action, lambda name: self.internal_action(deck, name))
        except DeckConnectionError:
            raise
        except (OSError, ValueError, KeyError) as exc:
            LOG.error("Aktion fehlgeschlagen: %s", exc)

    def handle_event(self, deck: DeckInterface, event: tuple[str, int, int | bool]) -> None:
        now = time.monotonic()
        self.last_input = now
        kind, index, value = event
        if kind == "key":
            pressed = bool(value)
            if index == self.settings.screensaver_hold_key:
                if pressed:
                    if self.screensaver_hold_started_at is None:
                        self.screensaver_hold_started_at = now
                        self.screensaver_hold_triggered = False
                    return

                self.screensaver_hold_started_at = None
                if self.screensaver_hold_triggered:
                    self.screensaver_hold_triggered = False
                    return
                if self.idle:
                    self.stop_screensaver(deck)
                    return
                self.dispatch_key(deck, index, True)
                return

            if index == self.settings.audio_device_hold_key:
                if pressed:
                    if self.audio_device_hold_started_at is None:
                        self.audio_device_hold_started_at = now
                        self.audio_device_hold_triggered = False
                    return

                self.audio_device_hold_started_at = None
                if self.audio_device_hold_triggered:
                    self.audio_device_hold_triggered = False
                    return
                if self.idle:
                    self.stop_screensaver(deck)
                    return
                self.dispatch_key(deck, index, True)
                return

            if self.idle:
                if pressed:
                    self.stop_screensaver(deck)
                return
            if pressed:
                self.dispatch_key(deck, index, True)
        else:
            if self.idle:
                self.stop_screensaver(deck)
                return
            direction = "right" if int(value) > 0 else "left"
            if not self.profile_runtime.on_encoder(
                self.profile_context(deck), index, direction
            ):
                encoder = self.settings.encoders.get(index, {})
                self.run_action(deck, encoder.get(direction))

    def check_screensaver_hold(self, deck: DeckInterface, now: float) -> None:
        if (
            self.screensaver_hold_started_at is None
            or self.screensaver_hold_triggered
            or now
            < self.screensaver_hold_started_at + self.settings.screensaver_hold_seconds
        ):
            return
        self.screensaver_hold_triggered = True
        self.toggle_screensaver(deck)
        LOG.info("Screensaver durch langes Halten des grossen Encoders umgeschaltet")

    def check_audio_device_hold(self, deck: DeckInterface, now: float) -> None:
        if (
            self.audio_device_hold_started_at is None
            or self.audio_device_hold_triggered
            or now
            < self.audio_device_hold_started_at + self.settings.audio_device_hold_seconds
        ):
            return
        self.audio_device_hold_triggered = True
        self.cycle_output_device(deck)

    def dispatch_key(
        self,
        deck: DeckInterface,
        index: int,
        pressed: bool,
    ) -> None:
        if index < 6:
            if self.profile_runtime.on_button(
                self.profile_context(deck), index, pressed
            ):
                return
        if pressed:
            self.run_action(deck, self._key_action(index))

    def _key_action(self, index: int) -> Action | None:
        if index < 6:
            return self.profile.buttons[index].action
        return self.settings.hardware_buttons.get(index)

    def tick_profile(self, deck: DeckInterface, now: float) -> None:
        self.profile_runtime.on_tick(self.profile_context(deck), now)

    def start_screensaver(self, deck: DeckInterface, now: float | None = None) -> None:
        if self.idle:
            return
        self.idle = True
        self.animation = self.animation or IdleAnimation()
        self.animation_frame = 0
        self.next_animation_frame = 0.0
        deck.clear_all()
        LOG.info("Screensaver gestartet")
        self.render_market_tiles(deck)
        self.update_idle(deck, time.monotonic() if now is None else now)

    def stop_screensaver(self, deck: DeckInterface) -> None:
        if not self.idle:
            return
        self.idle = False
        self.last_input = time.monotonic()
        if all(image is None for image in self.display.base):
            self.render_profile(deck)
        else:
            self.display.render(deck)
        LOG.info("Screensaver beendet")

    def toggle_screensaver(self, deck: DeckInterface, now: float | None = None) -> None:
        if self.idle:
            self.stop_screensaver(deck)
        else:
            self.start_screensaver(deck, now)

    def poll_foreground(self, deck: DeckInterface, now: float) -> None:
        if self.locked or now - self.last_window_poll < self.settings.foreground_poll_seconds:
            return
        self.last_window_poll = now
        window = self.foreground_provider()
        if not window.process_name or window.process_name.lower() in self.settings.ignored_processes:
            return
        new_index = self.profile_runtime.observe_process(
            window.process_name,
            now,
            self.settings.foreground_debounce_seconds,
        )
        if new_index is None:
            return
        LOG.info("Aktives Fenster: %s | %s", window.process_name, window.title)
        self.activate_profile(deck, new_index)

    def poll_profile_reload(self, deck: DeckInterface, now: float) -> None:
        if self.profile_reloader is None:
            return
        try:
            profiles = self.profile_reloader.poll(now)
            if profiles is None:
                return
            self.validate_profiles(profiles)
            old_name = self.profile.name
            old_locked = self.locked
            if self.profile_runtime.active_index is not None:
                self.profile_runtime.lifecycle.on_deactivate(self.profile_context(deck))

            self.profile_runtime = ProfileRuntime(profiles)
            self.profile_runtime.locked = old_locked
            if old_locked:
                target = next(
                    (
                        index
                        for index, profile in enumerate(self.profiles)
                        if profile.name == old_name
                    ),
                    0,
                )
            else:
                target = self.resolve_profile(self.foreground_provider().process_name)
            self.profile_runtime.reset_candidate(target, now)
            self.display.clear_overlays()
            self.activate_profile(deck, target)
            LOG.info("Entwicklungsmodus: %d Profile neu geladen", len(profiles))
        except (ImportError, OSError, RuntimeError, SyntaxError, TypeError, ValueError) as exc:
            LOG.error("Profil-Neuladen fehlgeschlagen; alter Stand bleibt aktiv: %s", exc)

    def update_idle(self, deck: DeckInterface, now: float) -> None:
        if not self.idle and now - self.last_input >= self.settings.idle_seconds:
            self.start_screensaver(deck, now)

        if not self.idle or now < self.next_animation_frame:
            return

        assert self.animation is not None
        for key, jpeg in enumerate(self.animation.get(self.animation_frame)):
            deck.set_key_jpeg(key, jpeg)
        self.animation_frame = (self.animation_frame + 1) % len(self.animation)
        self.next_animation_frame = now + 1 / self.settings.animation_fps

    def _connected_loop(self, deck: DeckInterface, deadline: float | None) -> None:
        # The controller restores the last layout written by the vendor software
        # after a USB restart. Always remove that persistent visual state before
        # drawing our own profile or screensaver.
        deck.clear_all()
        self.screensaver_hold_started_at = None
        self.screensaver_hold_triggered = False
        self.audio_device_hold_started_at = None
        self.audio_device_hold_triggered = False
        deck.set_brightness(self.settings.brightness)
        window = self.foreground_provider()
        initial_index = self.profile_index
        if window.process_name.lower() not in self.settings.ignored_processes:
            initial_index = self.resolve_profile(window.process_name)
        self.profile_runtime.reset_candidate(initial_index, time.monotonic())
        self.activate_profile(deck, initial_index)
        if self.idle:
            self.next_animation_frame = 0.0
        LOG.info("Controller aktiv. Strg+C beendet den Dienst.")

        while True:
            if deadline is not None and time.monotonic() >= deadline:
                LOG.info("Zeitlich begrenzter Lauf beendet.")
                return
            report = deck.read(timeout_ms=self.settings.hid_read_timeout_ms)
            event = decode_event(report)
            if event is not None:
                LOG.debug("Deck-Ereignis: %s", event)
                self.handle_event(deck, event)
            now = time.monotonic()
            self.check_screensaver_hold(deck, now)
            self.check_audio_device_hold(deck, now)
            self.poll_profile_reload(deck, now)
            self.poll_foreground(deck, now)
            self.poll_market(deck, now)
            self.tick_profile(deck, now)
            self.display.tick(deck, now, render_enabled=not self.idle)
            self.update_idle(deck, now)

    def run(self, run_seconds: float | None = None) -> None:
        deadline = time.monotonic() + run_seconds if run_seconds is not None else None
        waiting_logged = False
        try:
            while deadline is None or time.monotonic() < deadline:
                try:
                    with self.deck_factory() as deck:
                        if waiting_logged:
                            LOG.info("SOOMFON wieder verbunden.")
                        waiting_logged = False
                        self._connected_loop(deck, deadline)
                        return
                except (DeckConnectionError, OSError, RuntimeError) as exc:
                    if not waiting_logged:
                        LOG.warning("SOOMFON nicht verfuegbar: %s", exc)
                        LOG.info(
                            "Neuer Verbindungsversuch alle %.1f Sekunden.",
                            self.settings.reconnect_seconds,
                        )
                        waiting_logged = True
                    if deadline is not None:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return
                        time.sleep(min(self.settings.reconnect_seconds, remaining))
                    else:
                        time.sleep(self.settings.reconnect_seconds)
        except KeyboardInterrupt:
            LOG.info("Controller beendet.")


def run(
    config_path: Path,
    screensaver_now: bool = False,
    run_seconds: float | None = None,
    dev_reload: bool = False,
) -> None:
    service = ControllerService(config_path, dev_reload=dev_reload)
    if screensaver_now:
        service.last_input = 0.0
    if service.market_worker is not None:
        service.market_worker.start()
    try:
        service.run(run_seconds=run_seconds)
    finally:
        if service.market_worker is not None:
            service.market_worker.stop()
