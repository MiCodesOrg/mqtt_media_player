import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

HUB_TITLE = "MQTT Media Player"


@config_entries.HANDLERS.register(DOMAIN)
class MqttMediaPlayerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Create the single hub entry that watches for MQTT discovery.

        No YAML is required: add the integration once from the UI, and every
        discovered player then appears on its own.
        """
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

        return self.async_create_entry(title=HUB_TITLE, data={})

    async def async_step_import(self, import_info=None):
        """Enable through configuration.yaml (`mqtt_media_player:`)."""
        return await self.async_step_user({})

    async def async_step_mqtt(self, discovery_info=None):
        """Handle MQTT discovery by creating a per-device entry."""
        if discovery_info is None:
            return self.async_abort(reason="no_discovery_info")

        device_name = discovery_info.get("name", HUB_TITLE)

        # Check if already configured
        await self.async_set_unique_id(device_name)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=device_name,
            data=discovery_info,
        )
