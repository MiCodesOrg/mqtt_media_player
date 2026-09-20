import json
import logging
from functools import partial
from homeassistant.util.dt import utcnow
from homeassistant.components import media_source
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    async_process_play_media_url
)
from homeassistant.components.mqtt import (
    async_subscribe,
    async_publish,
    async_wait_for_mqtt_client,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .config import (
    discovery_prefix_from_entries,
    discovery_subscription,
    feature_names,
    parse_availability,
    parse_command_topics,
    parse_state_topics,
)
from .const import DOMAIN
from .state import MediaPlayerState, Role

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup entry point."""
    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available, make sure MQTT is set up correctly")
        return False

    player = MQTTMediaPlayer(hass, config_entry)
    async_add_entities([player])
    
    # Subscribe to the config topic to get media player configuration dynamically
    # Use the discovery topic if available, otherwise construct a wildcard pattern
    if "discovery_topic" in config_entry.data:
        CONFIG_TOPIC = config_entry.data["discovery_topic"]
    else:
        # For manually added devices, subscribe to the configured prefix.
        CONFIG_TOPIC = discovery_subscription(
            discovery_prefix_from_entries(hass.config_entries.async_entries("mqtt"))
        )
        
    unsubscribe_config = await async_subscribe(hass, CONFIG_TOPIC, player.handle_config)
    player.set_config_unsubscribe(unsubscribe_config)


class MQTTMediaPlayer(MediaPlayerEntity):
    """Representation of a MQTT Media Player."""
   
    def __init__(self, hass, config_entry):
        """Initialize the MQTT Media Player."""
        self._hass = hass
        self._config_entry = config_entry
        self._name = None
        self._model = MediaPlayerState(now=utcnow)
        self._removing = False
        self._subscribed = []
        self._config_unsubscribe = None
        self._availability_topics = {}
        self._state_topics = {}
        self._cmd_topics = {}
        self._device_config = {}

        if "discovery_data" in config_entry.data:
            disc_data = config_entry.data["discovery_data"]
            self._device_config = disc_data.get("device", {})
            if "name" in disc_data:
                self._name = disc_data.get("name")

    def set_config_unsubscribe(self, unsubscribe_callback):
        """Set the unsubscribe callback for the config topic."""
        self._config_unsubscribe = unsubscribe_callback

    async def async_added_to_hass(self):
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self._update_device_binding()

    def _update_device_binding(self):
        """Link entity to the official MQTT integration device page if it exists."""
        if not self._device_config or not self.registry_entry:
            return

        raw_ids = self._device_config.get("identifiers", [self._config_entry.title])
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]

        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)

        for dev_id in raw_ids:
            mqtt_device = dev_reg.async_get_device(identifiers={("mqtt", dev_id)})
            if mqtt_device:
                old_device_id = self.registry_entry.device_id
                if old_device_id != mqtt_device.id:
                    ent_reg.async_update_entity(self.entity_id, device_id=mqtt_device.id)
                    _LOGGER.info("Linked %s to official MQTT device '%s' (ID: %s)", self.entity_id, mqtt_device.name, mqtt_device.id)

                    # Remove old empty device entry if it belonged to mqtt_media_player and has no remaining entities
                    if old_device_id:
                        old_device = dev_reg.async_get(old_device_id)
                        if old_device and self._config_entry.entry_id in old_device.config_entries:
                            entities_on_old_device = er.async_entries_for_device(ent_reg, old_device_id)
                            if not entities_on_old_device:
                                dev_reg.async_remove_device(old_device_id)
                                _LOGGER.info("Removed empty device entry %s", old_device_id)
                break

    async def async_will_remove_from_hass(self):
        """Unsubscribe from MQTT topics when entity is removed."""
        if self._config_unsubscribe:
            self._config_unsubscribe()
            self._config_unsubscribe = None
        for subscription in self._subscribed:
            subscription()
        self._subscribed.clear()

    @property
    def device_info(self):
        """Return device registry information matching the official MQTT integration."""
        if not self._device_config:
            return {
                "identifiers": {(DOMAIN, self._config_entry.title)},
                "name": self._name or self._config_entry.title,
                "manufacturer": "MQTT Media Player",
            }

        raw_ids = self._device_config.get("identifiers", [self._config_entry.title])
        if isinstance(raw_ids, str):
            raw_ids = [raw_ids]

        # Include ("mqtt", id) so Home Assistant merges this entity onto the official MQTT device page
        identifiers = {("mqtt", dev_id) for dev_id in raw_ids}
        identifiers.add((DOMAIN, self._config_entry.title))

        info = {
            "identifiers": identifiers,
            "name": self._device_config.get("name", self._name or self._config_entry.title),
            "manufacturer": self._device_config.get("manufacturer", "MQTT Media Player"),
        }
        if model := self._device_config.get("model"):
            info["model"] = model
        if sw_version := self._device_config.get("sw_version"):
            info["sw_version"] = sw_version
        if via_device := self._device_config.get("via_device"):
            info["via_device"] = (DOMAIN, via_device)

        return info

    async def handle_config(self, message):
        """Handle incoming configuration from MQTT."""
        # Empty payload means the device is removed: drop the entity and its config entry.
        if not message.payload or message.payload.strip() == "":
            if self._removing:
                return
            self._removing = True
            entry_id = self._config_entry.entry_id
            if self.hass.config_entries.async_get_entry(entry_id) is None:
                return
            _LOGGER.info("Received empty config payload - removing %s", self._config_entry.title)
            self.hass.async_create_task(self.hass.config_entries.async_remove(entry_id))
            return
        
        try:
            config = json.loads(message.payload)
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Failed to parse config JSON: {e}")
            return
        
        # Extract device ID from the topic to match against our config entry
        # Topic format: homeassistant/media_player/[optional_prefix/]device_id/config
        topic_parts = message.topic.split('/')
        topic_device_id = topic_parts[-2]  # Get the part before '/config'
        
        # Only process if this message is for our device
        if topic_device_id != self._config_entry.title:
            _LOGGER.debug(f"Ignoring config for different device: {topic_device_id}")
            return
            
        _LOGGER.info(f"Received configuration: {config}")
        self._name = config.get("name")
        self._device_config = config.get("device", {})

        # Bind entity to official MQTT device if present
        self._update_device_binding()

        # Set the MQTT topics from the configuration
        self._availability_topics = parse_availability(config)
        self._state_topics = parse_state_topics(config)
        self._cmd_topics = parse_command_topics(config)
        self._model.set_availability_payloads(
            self._availability_topics["available"],
            self._availability_topics["not_available"],
        )

        # Unsubscribe from subscribed topics
        for subscription in self._subscribed:
            subscription()
        self._subscribed = []

        # Subscribe every configured state topic to the matching role
        for key, role in (
            ("state_topic", Role.STATE),
            ("title_topic", Role.TITLE),
            ("artist_topic", Role.ARTIST),
            ("album_topic", Role.ALBUM),
            ("duration_topic", Role.DURATION),
            ("position_topic", Role.POSITION),
            ("volume_topic", Role.VOLUME),
            ("albumart_topic", Role.ALBUMART),
            ("mediatype_topic", Role.MEDIATYPE),
            ("mute_topic", Role.MUTE),
            ("source_topic", Role.SOURCE),
        ):
            if (check_topic := self._state_topics[key]) is not None:
                self._subscribed.append(
                    await async_subscribe(self._hass, check_topic, partial(self._handle, role))
                )
        if (check_topic := self._availability_topics["availability_topic"]) is not None:
            self._subscribed.append(
                await async_subscribe(self._hass, check_topic, partial(self._handle, Role.AVAILABILITY))
            )

        self.async_write_ha_state()

    @property
    def supported_features(self):
        """Return supported features based on configured command topics."""
        features = MediaPlayerEntityFeature(0)
        for name in feature_names(self._cmd_topics):
            features |= getattr(MediaPlayerEntityFeature, name)
        return features

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._config_entry.title

    @property
    def state(self):
        if self._model.available is False:
            return "unavailable"
        return self._model.state

    @property
    def volume_level(self):
        return self._model.volume

    @property
    def is_volume_muted(self):
        return self._model.muted

    @property
    def source(self):
        return self._model.source

    @property
    def media_title(self):
        return self._model.title

    @property
    def media_artist(self):
        return self._model.artist

    @property
    def media_album_name(self):
        return self._model.album

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return self._model.media_type

    @property
    def media_position(self):
        """Position of player in percentage."""
        return self._model.position

    @property
    def media_duration(self):
        """Duration of current playing media in percentage."""
        return self._model.duration

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        return self._model.image_hash

    async def async_get_media_image(self):
        """Fetch media image of current playing image."""
        if self._model.album_art:
            return (self._model.album_art, "image/jpeg")
        return None, None

    async def _handle(self, role, message):
        """Apply an incoming payload for a role and publish the new state."""
        self._model.apply(role, message.payload)
        if role is Role.POSITION and self._model.position is not None:
            self._attr_media_position_updated_at = self._model.position_updated_at
        self.async_write_ha_state()

    async def async_media_play(self):
        """Send play command via MQTT."""
        if topic := self._cmd_topics.get("play_topic"):
            await async_publish(self._hass, topic, self._cmd_topics.get("play_payload", "Play"))

    async def async_media_pause(self):
        """Send pause command via MQTT."""
        if topic := self._cmd_topics.get("pause_topic"):
            await async_publish(self._hass, topic, self._cmd_topics.get("pause_payload", "Pause"))

    async def async_media_next_track(self):
        """Send next track command via MQTT."""
        if topic := self._cmd_topics.get("next_topic"):
            await async_publish(self._hass, topic, self._cmd_topics.get("next_payload", "Next"))

    async def async_media_previous_track(self):
        """Send previous track command via MQTT."""
        if topic := self._cmd_topics.get("previous_topic"):
            await async_publish(self._hass, topic, self._cmd_topics.get("previous_payload", "Previous"))

    async def async_media_play_pause(self):
        """Toggle play/pause via MQTT."""
        if topic := self._cmd_topics.get("playpause_topic"):
            await async_publish(self._hass, topic, self._cmd_topics.get("playpause_payload", "PlayPause"))

    async def async_mute_volume(self, mute):
        """Mute or unmute via MQTT."""
        if topic := self._cmd_topics.get("mute_topic"):
            payload = (
                self._cmd_topics.get("mute_on_payload", "mute")
                if mute
                else self._cmd_topics.get("mute_off_payload", "unmute")
            )
            self._model.set_muted(mute)
            await async_publish(self._hass, topic, payload)

    async def async_media_seek(self, position):
        """Seek to a position (seconds) via MQTT."""
        if topic := self._cmd_topics.get("seek_topic"):
            await async_publish(self._hass, topic, str(int(round(float(position)))))

    async def async_turn_on(self):
        """Turn the player on via MQTT."""
        if topic := self._cmd_topics.get("turnon_topic"):
            await async_publish(self._hass, topic, self._cmd_topics.get("turnon_payload", "on"))

    async def async_turn_off(self):
        """Turn the player off via MQTT."""
        if topic := self._cmd_topics.get("turnoff_topic"):
            await async_publish(self._hass, topic, self._cmd_topics.get("turnoff_payload", "off"))

    async def async_set_volume_level(self, volume):
        """Set the volume level via MQTT."""
        if topic := self._cmd_topics.get("volumeset_topic"):
            self._model.set_volume(volume)
            await async_publish(self._hass, topic, self._model.volume)

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Sends media to play."""
        if topic := self._cmd_topics.get("playmedia_topic"):
            if media_source.is_media_source_id(media_id):
                sourced_media = await media_source.async_resolve_media(self.hass, media_id)
                media_type = sourced_media.mime_type
                media_id = async_process_play_media_url(self.hass, sourced_media.url)
            media = {
                "media_type": media_type,
                "media_id": media_id,
            }
            await async_publish(self._hass, topic, json.dumps(media))

    async def async_browse_media(self, media_content_type, media_content_id):
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type,
        )
