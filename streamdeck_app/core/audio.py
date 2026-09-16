"""Lazy Windows Core Audio access with an injectable test interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AudioUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioState:
    percent: int
    muted: bool
    label: str = "SYSTEM"


@dataclass(frozen=True)
class AudioDeviceState:
    name: str


class AudioController(Protocol):
    def change_system_volume(self, delta_percent: int) -> AudioState: ...

    def toggle_system_mute(self) -> AudioState: ...

    def change_application_volume(
        self, process_id: int, process_name: str, delta_percent: int
    ) -> AudioState: ...

    def toggle_application_mute(self, process_id: int, process_name: str) -> AudioState: ...

    def change_microphone_volume(self, delta_percent: int) -> AudioState: ...

    def toggle_microphone_mute(self) -> AudioState: ...

    def cycle_output_device(self, preferred_names: tuple[str, ...]) -> AudioDeviceState: ...


class WindowsAudioController:
    """Accesses pycaw only when an audio action is actually requested."""

    @staticmethod
    def _endpoint():  # type: ignore[no-untyped-def]
        try:
            from pycaw.pycaw import AudioUtilities

            return AudioUtilities.GetSpeakers().EndpointVolume
        except Exception as exc:
            raise AudioUnavailableError(f"Windows-Audiogeraet nicht verfuegbar: {exc}") from exc

    @staticmethod
    def _state(endpoint, label: str = "SYSTEM") -> AudioState:  # type: ignore[no-untyped-def]
        try:
            return AudioState(
                percent=round(float(endpoint.GetMasterVolumeLevelScalar()) * 100),
                muted=bool(endpoint.GetMute()),
                label=label,
            )
        except Exception as exc:
            raise AudioUnavailableError(f"Audiostatus konnte nicht gelesen werden: {exc}") from exc

    def change_system_volume(self, delta_percent: int) -> AudioState:
        endpoint = self._endpoint()
        state = self._state(endpoint)
        target = max(0, min(100, state.percent + delta_percent))
        try:
            endpoint.SetMasterVolumeLevelScalar(target / 100, None)
            if state.muted and delta_percent > 0:
                endpoint.SetMute(False, None)
            return self._state(endpoint)
        except Exception as exc:
            raise AudioUnavailableError(f"Lautstaerke konnte nicht gesetzt werden: {exc}") from exc

    def toggle_system_mute(self) -> AudioState:
        endpoint = self._endpoint()
        state = self._state(endpoint)
        try:
            endpoint.SetMute(not state.muted, None)
            return self._state(endpoint)
        except Exception as exc:
            raise AudioUnavailableError(f"Stummschaltung fehlgeschlagen: {exc}") from exc

    @staticmethod
    def _application_volumes(process_id: int, process_name: str):  # type: ignore[no-untyped-def]
        try:
            from pycaw.pycaw import AudioUtilities

            target_name = process_name.casefold()
            volumes = []
            for session in AudioUtilities.GetAllSessions():
                try:
                    process = session.Process
                    name_matches = bool(
                        process and process.name().casefold() == target_name
                    )
                    if session.ProcessId == process_id or name_matches:
                        volumes.append(session.SimpleAudioVolume)
                except Exception:
                    continue
            if not volumes:
                raise AudioUnavailableError(
                    f"Keine aktive Audiositzung fuer {process_name or process_id}"
                )
            return volumes
        except AudioUnavailableError:
            raise
        except Exception as exc:
            raise AudioUnavailableError(f"Audiositzungen konnten nicht gelesen werden: {exc}") from exc

    @staticmethod
    def _application_state(volumes, process_name: str) -> AudioState:  # type: ignore[no-untyped-def]
        try:
            levels = [float(volume.GetMasterVolume()) for volume in volumes]
            muted = all(bool(volume.GetMute()) for volume in volumes)
            label = process_name.removesuffix(".exe").upper()[:7] or "APP"
            return AudioState(round(sum(levels) / len(levels) * 100), muted, label)
        except Exception as exc:
            raise AudioUnavailableError(f"App-Lautstaerke konnte nicht gelesen werden: {exc}") from exc

    def change_application_volume(
        self, process_id: int, process_name: str, delta_percent: int
    ) -> AudioState:
        volumes = self._application_volumes(process_id, process_name)
        try:
            for volume in volumes:
                current = float(volume.GetMasterVolume())
                target = max(0.0, min(1.0, current + delta_percent / 100))
                volume.SetMasterVolume(target, None)
                if bool(volume.GetMute()) and delta_percent > 0:
                    volume.SetMute(False, None)
            return self._application_state(volumes, process_name)
        except AudioUnavailableError:
            raise
        except Exception as exc:
            raise AudioUnavailableError(f"App-Lautstaerke konnte nicht gesetzt werden: {exc}") from exc

    def toggle_application_mute(self, process_id: int, process_name: str) -> AudioState:
        volumes = self._application_volumes(process_id, process_name)
        try:
            target = not all(bool(volume.GetMute()) for volume in volumes)
            for volume in volumes:
                volume.SetMute(target, None)
            return self._application_state(volumes, process_name)
        except AudioUnavailableError:
            raise
        except Exception as exc:
            raise AudioUnavailableError(f"App-Stummschaltung fehlgeschlagen: {exc}") from exc

    @staticmethod
    def _microphone_endpoint():  # type: ignore[no-untyped-def]
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            device = AudioUtilities.GetMicrophone()
            interface = device.Activate(
                IAudioEndpointVolume._iid_,
                CLSCTX_ALL,
                None,
            )
            return cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as exc:
            raise AudioUnavailableError(f"Windows-Mikrofon nicht verfuegbar: {exc}") from exc

    def change_microphone_volume(self, delta_percent: int) -> AudioState:
        endpoint = self._microphone_endpoint()
        state = self._state(endpoint, "MIC")
        target = max(0, min(100, state.percent + delta_percent))
        try:
            endpoint.SetMasterVolumeLevelScalar(target / 100, None)
            if state.muted and delta_percent > 0:
                endpoint.SetMute(False, None)
            return self._state(endpoint, "MIC")
        except Exception as exc:
            raise AudioUnavailableError(f"Mikrofonpegel konnte nicht gesetzt werden: {exc}") from exc

    def toggle_microphone_mute(self) -> AudioState:
        endpoint = self._microphone_endpoint()
        state = self._state(endpoint, "MIC")
        try:
            endpoint.SetMute(not state.muted, None)
            return self._state(endpoint, "MIC")
        except Exception as exc:
            raise AudioUnavailableError(f"Mikrofon-Mute fehlgeschlagen: {exc}") from exc

    def cycle_output_device(self, preferred_names: tuple[str, ...]) -> AudioDeviceState:
        try:
            from pycaw.constants import DEVICE_STATE, EDataFlow, ERole
            from pycaw.pycaw import AudioUtilities

            devices = list(
                AudioUtilities.GetAllDevices(
                    data_flow=EDataFlow.eRender.value,
                    device_state=DEVICE_STATE.ACTIVE.value,
                )
            )
            if preferred_names:
                filters = tuple(name.casefold() for name in preferred_names)
                devices = [
                    device
                    for device in devices
                    if any(name in device.FriendlyName.casefold() for name in filters)
                ]
            if len(devices) < 2:
                raise AudioUnavailableError("Weniger als zwei passende Ausgabegeraete aktiv")

            current_id = AudioUtilities.GetSpeakers().id
            current_index = next(
                (index for index, device in enumerate(devices) if device.id == current_id),
                -1,
            )
            target = devices[(current_index + 1) % len(devices)]
            AudioUtilities.SetDefaultDevice(
                target.id,
                roles=[ERole.eConsole, ERole.eMultimedia, ERole.eCommunications],
            )
            return AudioDeviceState(target.FriendlyName)
        except AudioUnavailableError:
            raise
        except Exception as exc:
            raise AudioUnavailableError(f"Ausgabegeraet konnte nicht gewechselt werden: {exc}") from exc
