import json
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.components.mqtt import (
    async_subscribe,
    async_publish,
    async_wait_for_mqtt_client,
)

from homeassistant.helpers import config_validation as cv

from .config import (
    discovery_config_topic,
    discovery_prefix_from_entries,
    discovery_subscription,
)
from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


def _get_discovery_prefix(hass: HomeAssistant):
    """Read the discovery prefix configured in Home Assistant's MQTT integration."""
    return discovery_prefix_from_entries(hass.config_entries.async_entries("mqtt"))

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration using YAML (if needed)."""
    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration is not available, make sure MQTT is set up correctly")
        return False

    # Subscribe to the discovery topic with a wildcard to catch nested paths,
    # honouring the discovery prefix configured in the MQTT integration.
    discovery_topic = discovery_subscription(_get_discovery_prefix(hass))
    
    async def mqtt_discovery_callback(message):
        """Handle MQTT discovery messages."""
        # Only process config topics
        if not message.topic.endswith("/config"):
            return
            
        # Skip empty payloads (device removal)
        if not message.payload or message.payload.strip() == "":
            _LOGGER.debug(f"Ignoring empty payload on {message.topic}")
            return
            
        try:
            config_data = json.loads(message.payload)
            
            # Extract device_id from topic (the part before /config)
            topic_parts = message.topic.split("/")
            device_id = topic_parts[-2]  # Get the part right before '/config'
            
            _LOGGER.info(f"Discovered MQTT media player: {device_id} from topic {message.topic}")
            
            # Check if this device is already configured
            current_entries = hass.config_entries.async_entries(DOMAIN)
            for entry in current_entries:
                if entry.title == device_id:
                    _LOGGER.debug(f"Device {device_id} already configured")
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
                    }
                )
            )
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Failed to parse MQTT discovery JSON from {message.topic}: {e}")
        except Exception as e:
            _LOGGER.error(f"Error processing MQTT discovery: {e}")
    
    await async_subscribe(hass, discovery_topic, mqtt_discovery_callback)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the integration from the UI."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Handle removal of the integration."""
    
    # Clear the MQTT config by publishing empty payload
    if "discovery_topic" in entry.data:
        # Use the stored discovery topic
        config_topic = entry.data["discovery_topic"]
    else:
        # Construct the config topic for manually added devices
        config_topic = discovery_config_topic(entry.title, _get_discovery_prefix(hass))
    
    if await async_wait_for_mqtt_client(hass):
        try:
            await async_publish(hass, config_topic, "", retain=True)
            _LOGGER.info(f"Cleared MQTT config for {entry.title} at {config_topic}")
        except Exception as e:
            _LOGGER.error(f"Failed to clear MQTT config: {e}")
    
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
