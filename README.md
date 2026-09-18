# MQTT Media Player

Easiest way to add a custom MQTT Media Player with full auto-discovery support.

## Features

- 🔍 **MQTT Auto-Discovery** - Devices automatically appear in Home Assistant
- 🎵 **Full Media Control** - Play, pause, skip, volume, and more
- 🖼️ **Album Art Support** - Display cover art from MQTT
- 📊 **Progress Tracking** - Track position and duration
- 🔌 **Availability Monitoring** - Know when devices are online/offline
- 📁 **Media Browser** - Browse and play media from Home Assistant
- 🔇 **Mute** - Mute / unmute with state feedback
- ⏩ **Seek** - Seek to an absolute position (seconds)
- ⏻ **Power** - Turn on / turn off commands
- 🧩 **Source** - Report the current source (e.g. app name)

## Installation
Easiest install is via [HACS](https://hacs.xyz/):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bkbilly&repository=mqtt_media_player&category=integration)

## Configuration

### MQTT Discovery Message

Publish a JSON configuration message to `homeassistant/media_player/{device_id}/config`:

```json
{
  "availability": {
    "topic": "myplayer/available",
    "payload_available": "ON",
    "payload_not_available": "OFF"
  },
  "name": "My Custom Player",
  "state_state_topic": "myplayer/state",
  "state_title_topic": "myplayer/title",
  "state_artist_topic": "myplayer/artist",
  "state_album_topic": "myplayer/album",
  "state_duration_topic": "myplayer/duration",
  "state_position_topic": "myplayer/position",
  "state_volume_topic": "myplayer/volume",
  "state_albumart_topic": "myplayer/albumart",
  "state_mediatype_topic": "myplayer/mediatype",
  "command_volume_topic": "myplayer/set_volume",
  "command_play_topic": "myplayer/play",
  "command_play_payload": "play",
  "command_pause_topic": "myplayer/pause",
  "command_pause_payload": "pause",
  "command_playpause_topic": "myplayer/playpause",
  "command_playpause_payload": "playpause",
  "command_next_topic": "myplayer/next",
  "command_next_payload": "next",
  "command_previous_topic": "myplayer/previous",
  "command_previous_payload": "previous",
  "command_playmedia_topic": "myplayer/playmedia",
  "state_mute_topic": "myplayer/mute",
  "command_mute_topic": "myplayer/set_mute",
  "command_mute_on_payload": "mute",
  "command_mute_off_payload": "unmute",
  "command_seek_topic": "myplayer/seek",
  "command_turn_on_topic": "myplayer/turn_on",
  "command_turn_on_payload": "on",
  "command_turn_off_topic": "myplayer/turn_off",
  "command_turn_off_payload": "off",
  "state_source_topic": "myplayer/source"
}
```


### Configuration Options

| Variables                | Description                                              | Topic               | Payload   |
|--------------------------|----------------------------------------------------------|---------------------|-----------|
| availability             | Availability configuration object                        | -                   |           |
| ↳ topic                  | Availability topic                                       | myplayer/available  |           |
| ↳ payload_available      | Payload when device is available                         | -                   | online    |
| ↳ payload_unavailable    | Payload when device is unavailable                       | -                   | offline   |
| name                     | The name of the Media Player                             | -                   | MyPlayer  |
| state_state_topic        | Media Player state topic                                 | myplayer/state      |           |
| state_title_topic        | Track Title                                              | myplayer/title      |           |
| state_artist_topic       | Track Artist                                             | myplayer/artist     |           |
| state_album_topic        | Track Album                                              | myplayer/album      |           |
| state_duration_topic     | Track Duration (int)                                     | myplayer/duration   |           |
| state_position_topic     | Track Position (int)                                     | myplayer/position   |           |
| state_albumart_topic     | Thumbnail (byte)                                         | myplayer/albumart   |           |
| state_mediatype_topic    | Media Type (music, video)                                | myplayer/mediatype  |           |
| state_volume_topic       | Current system volume                                    | myplayer/volume     |           |
| command_volume_topic     | Set System volume                                        | myplayer/volumeset  |           |
| command_play_topic       | Play media                                               | myplayer/play       | Play      |
| command_pause_topic      | Pause media                                              | myplayer/pause      | Pause     |
| command_playpause_topic  | PlayPause media                                          | myplayer/playpause  | PlayPause |
| command_next_topic       | Go to next track                                         | myplayer/next       | Next      |
| command_previous_topic   | Go to previous track                                     | myplayer/previous   | Previous  |
| command_playmedia_topic  | Support TTS, playing media, etc...                       | myplayer/playmedia  |           |
| state_mute_topic         | Mute state (`mute`/`unmute`, `on`/`off`, `true`/`false`) | myplayer/mute       |           |
| command_mute_topic       | Set mute                                                 | myplayer/set_mute   | mute      |
| ↳ command_mute_on_payload | Payload sent to mute                                    | -                   | mute      |
| ↳ command_mute_off_payload| Payload sent to unmute                                  | -                   | unmute    |
| command_seek_topic       | Seek to position (int seconds)                           | myplayer/seek       |           |
| command_turn_on_topic    | Turn on                                                  | myplayer/turn_on    | on        |
| command_turn_off_topic   | Turn off                                                 | myplayer/turn_off   | off       |
| state_source_topic       | Current source (e.g. app name)                           | myplayer/source     |           |

### State Values

The `state_state_topic` should publish one of these values:
- `playing` - Media is currently playing
- `paused` - Media is paused
- `idle` - Player is idle
- `off` - Player is off
- `stopped` - Playback stopped

### Album Art

Album art should be published as a base64-encoded image (JPEG recommended) to the `state_albumart_topic`.

### Mute, Seek, Power and Source

All of these are optional; the entity only advertises the matching feature when the topic is configured.

- **Mute**: publish `mute`/`unmute` (also `on`/`off`, `true`/`false`) on `state_mute_topic`; Home Assistant sends `command_mute_on_payload` / `command_mute_off_payload` on `command_mute_topic`.
- **Seek**: Home Assistant publishes the target position in **seconds** on `command_seek_topic`.
- **Power**: `command_turn_on_topic` / `command_turn_off_topic` receive their configured payloads.
- **Source**: `state_source_topic` is shown as the entity `source` attribute (read-only), useful for an app/package name.
- **Play/Pause**: Home Assistant drives `play` and `pause` separately (there is no `PLAY_PAUSE` feature in current Home Assistant); `command_playpause_topic` is kept for the optional `async_media_play_pause` path.
