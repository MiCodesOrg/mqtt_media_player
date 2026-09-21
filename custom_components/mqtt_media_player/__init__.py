import json
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.components.mqtt import (
    async_subscribe,
    async_publish,
    async_wait_for_mqtt_client,
)

from .config import (
    discovery_config_topic,
    discovery_prefix_from_entries,
    discovery_subscription,
)
from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]

# The single "hub" entry created from the UI (or from configuration.yaml); its
# unique_id marks it apart from the per-device entries created by discovery.
HUB_UNIQUE_ID = DOMAIN


def _get_discovery_prefix(hass: HomeAssistant):
    """Read the discovery prefix configured in Home Assistant's MQTT integration."""
    return discovery_prefix_from_entries(hass.config_entries.async_entries("mqtt"))


async def async_setup(hass: HomeAssistant, config: dict):
    """Optional YAML activation (`mqtt_media_player:`): create the hub entry."""
    if DOMAIN not in config:
        return True
    hass.async_create_task(
        hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"})
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the hub entry (MQTT discovery watch) or a discovered device."""
    if entry.unique_id == HUB_UNIQUE_ID:
        return await _async_setup_hub(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_setup_hub(hass: HomeAssistant, entry: ConfigEntry):
    """Subscribe to the MQTT discovery topic and create per-device entries."""
    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available, make sure MQTT is set up correctly")
        return False

    # Subscribe to the discovery topic with a wildcard to catch nested paths,
    # honouring the discovery prefix configured in the MQTT integration.
    discovery_topic = discovery_subscription(_get_discovery_prefix(hass))

    async def mqtt_discovery_callback(message):
        """Handle MQTT discovery messages."""
        if not message.topic.endswith("/config"):
            return

        # Skip empty payloads (device removal)
        if not message.payload or message.payload.strip() == "":
            _LOGGER.debug("Ignoring empty payload on %s", message.topic)
            return

        try:
            config_data = json.loads(message.payload)

            # Extract device_id from topic (the part before /config)
            device_id = message.topic.split("/")[-2]

            _LOGGER.info("Discovered MQTT media player: %s from topic %s", device_id, message.topic)

            # Check if this device is already configured
            for existing in hass.config_entries.async_entries(DOMAIN):
                if existing.title == device_id:
                    _LOGGER.debug("Device %s already configured", device_id)
                    return

            # Create a new config entry for the discovered device
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "mqtt"},
                    data={
                        "name": device_id,
                        "discovery_topic": message.topic,
                        "discovery_data": config_data,
                    },
                )
            )
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse MQTT discovery JSON from %s: %s", message.topic, e)
        except Exception as e:
            _LOGGER.error("Error processing MQTT discovery: %s", e)

    unsubscribe = await async_subscribe(hass, discovery_topic, mqtt_discovery_callback)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = unsubscribe
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the hub (stop watching) or one discovered device."""
    if entry.unique_id == HUB_UNIQUE_ID:
        unsubscribe = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if unsubscribe:
            unsubscribe()
        return True

    # Clear the MQTT config by publishing empty payload
    if "discovery_topic" in entry.data:
        config_topic = entry.data["discovery_topic"]
    else:
        config_topic = discovery_config_topic(entry.title, _get_discovery_prefix(hass))

    if await async_wait_for_mqtt_client(hass):
        try:
            await async_publish(hass, config_topic, "", retain=True)
            _LOGGER.info("Cleared MQTT config for %s at %s", entry.title, config_topic)
        except Exception as e:
            _LOGGER.error("Failed to clear MQTT config: %s", e)

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
