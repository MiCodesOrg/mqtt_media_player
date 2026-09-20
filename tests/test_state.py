"""Unit tests for the pure media player state (no Home Assistant required)."""
import base64
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "mqtt_media_player"
    / "state.py"
)
_spec = importlib.util.spec_from_file_location("mqp_state", _MODULE_PATH)
_state_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_state_module)

MediaPlayerState = _state_module.MediaPlayerState
Role = _state_module.Role


def _state(**kwargs):
    return MediaPlayerState(**kwargs)


def test_state_is_lowercased_and_cleared():
    state = _state()
    state.apply(Role.STATE, "PLAYING")
    assert state.state == "playing"
    state.apply(Role.STATE, "  ")
    assert state.state is None


def test_text_roles_set_and_clear():
    state = _state()
    state.apply(Role.TITLE, "Song")
    state.apply(Role.ARTIST, "Artist")
    state.apply(Role.ALBUM, "Album")
    state.apply(Role.SOURCE, "SmartTube")
    assert (state.title, state.artist, state.album, state.source) == (
        "Song",
        "Artist",
        "Album",
        "SmartTube",
    )

    state.apply(Role.TITLE, "")
    assert state.title is None


def test_duration_parses_ints_and_clears():
    state = _state()
    state.apply(Role.DURATION, "240")
    assert state.duration == 240
    state.apply(Role.DURATION, "abc")
    assert state.duration is None


def test_position_sets_the_updated_at_timestamp():
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = _state(now=lambda: moment)
    state.apply(Role.POSITION, "40")
    assert state.position == 40
    assert state.position_updated_at == moment


def test_position_keeps_the_previous_timestamp_when_cleared():
    moment = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = _state(now=lambda: moment)
    state.apply(Role.POSITION, "40")
    state.apply(Role.POSITION, "")
    assert state.position is None
    assert state.position_updated_at == moment


def test_volume_defaults_to_zero_and_keeps_the_last_value_on_error():
    state = _state()
    state.apply(Role.VOLUME, "")
    assert state.volume == 0.0
    state.apply(Role.VOLUME, "0.5")
    assert state.volume == 0.5
    state.apply(Role.VOLUME, "loud")
    assert state.volume == 0.5


def test_album_art_is_decoded_and_hashed():
    state = _state()
    state.apply(Role.ALBUMART, base64.b64encode(b"cover").decode())
    assert state.album_art == b"cover"
    assert state.image_hash is not None
    state.apply(Role.ALBUMART, "not base64 !!")
    assert state.album_art is None
    assert state.image_hash is None


def test_media_type_defaults_to_music():
    state = _state()
    state.apply(Role.MEDIATYPE, "video")
    assert state.media_type == "video"
    state.apply(Role.MEDIATYPE, "")
    assert state.media_type == "music"


def test_mute_parses_both_vocabularies():
    state = _state()
    for payload in ("mute", "on", "true", "1"):
        state.apply(Role.MUTE, payload)
        assert state.muted is True
    for payload in ("unmute", "off", "false", "0"):
        state.apply(Role.MUTE, payload)
        assert state.muted is False
    state.apply(Role.MUTE, "")
    assert state.muted is None


def test_availability_uses_the_configured_payloads():
    state = _state()
    state.apply(Role.AVAILABILITY, "online")
    assert state.available is True
    state.apply(Role.AVAILABILITY, "offline")
    assert state.available is False

    state.set_availability_payloads("ON", "OFF")
    state.apply(Role.AVAILABILITY, "ON")
    assert state.available is True
    state.apply(Role.AVAILABILITY, "something")
    assert state.available is True


def test_set_helpers():
    state = _state()
    state.set_volume(0.333)
    assert state.volume == 0.33
    state.set_muted(True)
    assert state.muted is True
