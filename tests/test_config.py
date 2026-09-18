"""Unit tests for the discovery payload parser (no Home Assistant required)."""
import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "mqtt_media_player"
    / "config.py"
)
_spec = importlib.util.spec_from_file_location("mqp_config", _MODULE_PATH)
config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(config)

SAMPLE = {
    "availability": {
        "topic": "p/available",
        "payload_available": "ON",
        "payload_not_available": "OFF",
    },
    "state_state_topic": "p/state",
    "state_mute_topic": "p/mute",
    "state_source_topic": "p/source",
    "command_play_topic": "p/cmd/play",
    "command_pause_topic": "p/cmd/pause",
    "command_playpause_topic": "p/cmd/playpause",
    "command_next_topic": "p/cmd/next",
    "command_previous_topic": "p/cmd/previous",
    "command_volume_topic": "p/cmd/volume",
    "command_mute_topic": "p/cmd/mute",
    "command_seek_topic": "p/cmd/seek",
    "command_turn_on_topic": "p/cmd/on",
    "command_turn_off_topic": "p/cmd/off",
}


def test_availability_is_parsed_with_payloads():
    assert config.parse_availability(SAMPLE) == {
        "availability_topic": "p/available",
        "available": "ON",
        "not_available": "OFF",
    }


def test_state_topics_include_mute_and_source():
    state = config.parse_state_topics(SAMPLE)
    assert state["state_topic"] == "p/state"
    assert state["mute_topic"] == "p/mute"
    assert state["source_topic"] == "p/source"


def test_command_payload_defaults():
    cmd = config.parse_command_topics(SAMPLE)
    assert cmd["mute_on_payload"] == "mute"
    assert cmd["mute_off_payload"] == "unmute"
    assert cmd["turnon_payload"] == "on"
    assert cmd["turnoff_payload"] == "off"


def test_new_command_keys_enable_their_features():
    names = config.feature_names(config.parse_command_topics(SAMPLE))
    for expected in (
        "PLAY",
        "PAUSE",
        "NEXT_TRACK",
        "PREVIOUS_TRACK",
        "VOLUME_SET",
        "VOLUME_STEP",
        "VOLUME_MUTE",
        "SEEK",
        "TURN_ON",
        "TURN_OFF",
    ):
        assert expected in names


def test_empty_config_only_browses():
    assert config.feature_names(config.parse_command_topics({})) == {"BROWSE_MEDIA"}


def test_discovery_topics_follow_the_prefix():
    assert config.discovery_subscription() == "homeassistant/media_player/#"
    assert config.discovery_subscription("hass") == "hass/media_player/#"
    assert config.discovery_config_topic("dev", "hass") == "hass/media_player/dev/config"


def test_discovery_prefix_from_entries():
    class Entry:
        def __init__(self, options, data):
            self.options = options
            self.data = data

    assert config.discovery_prefix_from_entries([Entry({}, {})]) is None
    assert (
        config.discovery_prefix_from_entries(
            [Entry({}, {}), Entry({"discovery_prefix": "hass"}, {})]
        )
        == "hass"
    )
    assert (
        config.discovery_prefix_from_entries([Entry({}, {"discovery_prefix": "custom"})])
        == "custom"
    )
