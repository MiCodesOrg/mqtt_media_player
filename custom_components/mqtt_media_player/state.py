"""Pure media player state: applies incoming payloads to typed values.

Kept free of any Home Assistant import so it can be unit-tested on its own.
"""

import base64
import binascii
import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum

_LOGGER = logging.getLogger(__name__)

_MUTE_ON = ("mute", "muted", "on", "true", "1")
_MUTE_OFF = ("unmute", "unmuted", "off", "false", "0")


class Role(Enum):
    """The kind of value an incoming payload carries."""

    STATE = "state"
    TITLE = "title"
    ARTIST = "artist"
    ALBUM = "album"
    DURATION = "duration"
    POSITION = "position"
    VOLUME = "volume"
    ALBUMART = "albumart"
    MEDIATYPE = "mediatype"
    MUTE = "mute"
    SOURCE = "source"
    SUMMARY = "summary"
    SEASON = "season"
    EPISODE = "episode"
    SERIES = "series"
    YEAR = "year"
    AVAILABILITY = "availability"


class MediaPlayerState:
    """The last values observed for a discovered player, independent of Home Assistant."""

    def __init__(
        self,
        available_payload="online",
        not_available_payload="offline",
        now=lambda: datetime.now(timezone.utc),
    ):
        self._now = now
        self._available_payload = available_payload
        self._not_available_payload = not_available_payload

        self.available = None
        self.state = None
        self.volume = 0.0
        self.title = None
        self.artist = None
        self.album = None
        self.duration = None
        self.position = None
        self.position_updated_at = None
        self.album_art = None
        self.media_type = "music"
        self.muted = None
        self.source = None
        self.summary = None
        self.season = None
        self.episode = None
        self.series_title = None
        self.year = None

    def set_availability_payloads(self, available_payload, not_available_payload):
        self._available_payload = available_payload
        self._not_available_payload = not_available_payload

    def set_volume(self, volume):
        self.volume = round(float(volume), 2)

    def set_muted(self, muted):
        self.muted = bool(muted)

    @property
    def image_hash(self):
        if self.album_art:
            return hashlib.md5(self.album_art).hexdigest()[:5]
        return None

    def apply(self, role, payload):
        if role is Role.AVAILABILITY:
            self._apply_availability(payload)
        elif role is Role.STATE:
            self.state = payload.strip().lower() if payload and payload.strip() else None
        elif role is Role.TITLE:
            self.title = _text_or_none(payload)
        elif role is Role.ARTIST:
            self.artist = _text_or_none(payload)
        elif role is Role.ALBUM:
            self.album = _text_or_none(payload)
        elif role is Role.SOURCE:
            self.source = _text_or_none(payload)
        elif role is Role.SUMMARY:
            self.summary = _text_or_none(payload)
        elif role is Role.SEASON:
            self.season = _text_or_none(payload)
        elif role is Role.EPISODE:
            self.episode = _text_or_none(payload)
        elif role is Role.SERIES:
            self.series_title = _text_or_none(payload)
        elif role is Role.YEAR:
            self.year = _text_or_none(payload)
        elif role is Role.DURATION:
            self.duration = _int_or_none(payload)
        elif role is Role.POSITION:
            self._apply_position(payload)
        elif role is Role.VOLUME:
            self._apply_volume(payload)
        elif role is Role.ALBUMART:
            self._apply_album_art(payload)
        elif role is Role.MEDIATYPE:
            self.media_type = _text_or_none(payload) or "music"
        elif role is Role.MUTE:
            self._apply_mute(payload)

    def _apply_availability(self, payload):
        if payload == self._available_payload:
            self.available = True
        elif payload == self._not_available_payload:
            self.available = False

    def _apply_position(self, payload):
        value = _int_or_none(payload)
        self.position = value
        if value is not None:
            self.position_updated_at = self._now()

    def _apply_volume(self, payload):
        if not payload or not payload.strip():
            self.volume = 0.0
            return
        try:
            self.volume = float(payload)
        except (ValueError, TypeError):
            _LOGGER.debug("Invalid volume payload: %s", payload)

    def _apply_album_art(self, payload):
        if not payload or not payload.strip():
            self.album_art = None
            return
        try:
            self.album_art = base64.b64decode(payload.replace("\n", ""))
        except (binascii.Error, TypeError, ValueError) as error:
            _LOGGER.debug("Failed to decode album art: %s", error)
            self.album_art = None

    def _apply_mute(self, payload):
        value = (payload or "").strip().lower()
        if not value:
            self.muted = None
        elif value in _MUTE_ON:
            self.muted = True
        elif value in _MUTE_OFF:
            self.muted = False
        else:
            _LOGGER.debug("Unrecognised mute payload: %s", payload)


def _text_or_none(payload):
    return payload if payload and payload.strip() else None


def _int_or_none(payload):
    if not payload or not payload.strip():
        return None
    try:
        return int(payload)
    except (ValueError, TypeError):
        return None
