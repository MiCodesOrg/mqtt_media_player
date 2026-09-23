"""Pure parsing of the MQTT discovery payload.

Kept free of any Home Assistant import so it can be unit-tested on its own.
"""

DEFAULT_AVAILABLE = "online"
DEFAULT_NOT_AVAILABLE = "offline"
DEFAULT_MUTE_ON = "mute"
DEFAULT_MUTE_OFF = "unmute"
DEFAULT_TURN_ON = "on"
DEFAULT_TURN_OFF = "off"
DEFAULT_DISCOVERY_PREFIX = "homeassistant"


def discovery_subscription(prefix=None):
    """Return the wildcard subscription for media_player discovery configs."""
    return f"{(prefix or DEFAULT_DISCOVERY_PREFIX).strip('/')}/media_player/#"


def discovery_config_topic(device_id, prefix=None):
    """Return the discovery config topic for a given device."""
    return f"{(prefix or DEFAULT_DISCOVERY_PREFIX).strip('/')}/media_player/{device_id}/config"


def discovery_prefix_from_entries(entries):
    """Return the discovery prefix from MQTT config entries, if configured."""
    for entry in entries:
        prefix = entry.options.get("discovery_prefix") or entry.data.get("discovery_prefix")
        if prefix:
            return prefix
    return None


def parse_availability(config):
    """Return the availability topics/payloads."""
    availability = config.get("availability") or {}
    return {
        "availability_topic": availability.get("topic"),
        "available": availability.get("payload_available", DEFAULT_AVAILABLE),
        "not_available": availability.get("payload_not_available", DEFAULT_NOT_AVAILABLE),
    }


def parse_state_topics(config):
    """Return the state topics map."""
    return {
        "state_topic": config.get("state_state_topic"),
        "title_topic": config.get("state_title_topic"),
        "artist_topic": config.get("state_artist_topic"),
        "album_topic": config.get("state_album_topic"),
        "duration_topic": config.get("state_duration_topic"),
        "position_topic": config.get("state_position_topic"),
        "volume_topic": config.get("state_volume_topic"),
        "albumart_topic": config.get("state_albumart_topic"),
        "mediatype_topic": config.get("state_mediatype_topic"),
        "mute_topic": config.get("state_mute_topic"),
        "source_topic": config.get("state_source_topic"),
        "summary_topic": config.get("state_summary_topic"),
        "season_topic": config.get("state_season_topic"),
        "episode_topic": config.get("state_episode_topic"),
        "series_topic": config.get("state_series_topic"),
        "year_topic": config.get("state_year_topic"),
    }


def parse_command_topics(config):
    """Return the command topics map, with default payloads filled in."""
    return {
        "volumeset_topic": config.get("command_volume_topic"),
        "play_topic": config.get("command_play_topic"),
        "play_payload": config.get("command_play_payload", "Play"),
        "pause_topic": config.get("command_pause_topic"),
        "pause_payload": config.get("command_pause_payload", "Pause"),
        "playpause_topic": config.get("command_playpause_topic"),
        "playpause_payload": config.get("command_playpause_payload", "PlayPause"),
        "next_topic": config.get("command_next_topic"),
        "next_payload": config.get("command_next_payload", "Next"),
        "previous_topic": config.get("command_previous_topic"),
        "previous_payload": config.get("command_previous_payload", "Previous"),
        "playmedia_topic": config.get("command_playmedia_topic"),
        "mute_topic": config.get("command_mute_topic"),
        "mute_on_payload": config.get("command_mute_on_payload", DEFAULT_MUTE_ON),
        "mute_off_payload": config.get("command_mute_off_payload", DEFAULT_MUTE_OFF),
        "seek_topic": config.get("command_seek_topic"),
        "turnon_topic": config.get("command_turn_on_topic"),
        "turnon_payload": config.get("command_turn_on_payload", DEFAULT_TURN_ON),
        "turnoff_topic": config.get("command_turn_off_topic"),
        "turnoff_payload": config.get("command_turn_off_payload", DEFAULT_TURN_OFF),
    }


def feature_names(command_topics):
    """Return the MediaPlayerEntityFeature member names enabled by the command topics."""
    names = {"BROWSE_MEDIA"}
    if command_topics.get("play_topic") or command_topics.get("playpause_topic"):
        names.add("PLAY")
    if command_topics.get("pause_topic") or command_topics.get("playpause_topic"):
        names.add("PAUSE")
    if command_topics.get("next_topic"):
        names.add("NEXT_TRACK")
    if command_topics.get("previous_topic"):
        names.add("PREVIOUS_TRACK")
    if command_topics.get("volumeset_topic"):
        names.update(("VOLUME_SET", "VOLUME_STEP"))
    if command_topics.get("playmedia_topic"):
        names.add("PLAY_MEDIA")
    if command_topics.get("mute_topic"):
        names.add("VOLUME_MUTE")
    if command_topics.get("seek_topic"):
        names.add("SEEK")
    if command_topics.get("turnon_topic"):
        names.add("TURN_ON")
    if command_topics.get("turnoff_topic"):
        names.add("TURN_OFF")
    return names
