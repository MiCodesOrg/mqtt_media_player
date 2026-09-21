"""Activation flow tests (UI hub entry + optional YAML), without Home Assistant installed.

`config_flow.py` only needs a tiny surface of `homeassistant.config_entries` and
`voluptuous`, both stubbed here, so the suite stays runnable with plain pytest.
"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "mqtt_media_player"

_registered_unique_ids = set()


class _AbortFlow(Exception):
    pass


def _install_stubs():
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = lambda *args, **kwargs: {}
    sys.modules["voluptuous"] = voluptuous

    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.domain = domain

        def __init__(self):
            self._unique_id = None
            self.form_step = None
            self.created = None

        async def async_set_unique_id(self, unique_id):
            self._unique_id = unique_id

        def _abort_if_unique_id_configured(self):
            if self._unique_id in _registered_unique_ids:
                raise _AbortFlow(self._unique_id)

        def async_show_form(self, step_id, data_schema=None, **kwargs):
            self.form_step = step_id
            return {"type": "form", "step_id": step_id}

        def async_create_entry(self, title, data):
            _registered_unique_ids.add(self._unique_id)
            self.created = {"title": title, "data": data}
            return {"type": "create_entry", **self.created}

        def async_abort(self, reason):
            return {"type": "abort", "reason": reason}

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = ConfigFlow
    config_entries.HANDLERS = types.SimpleNamespace(register=lambda domain: (lambda cls: cls))

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.config_entries = config_entries

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries


_install_stubs()

_package = types.ModuleType("mqp")
_package.__path__ = [str(MODULE_DIR)]
sys.modules["mqp"] = _package
importlib.import_module("mqp.const")

_spec = importlib.util.spec_from_file_location("mqp.config_flow", MODULE_DIR / "config_flow.py")
config_flow = importlib.util.module_from_spec(_spec)
sys.modules["mqp.config_flow"] = config_flow
_spec.loader.exec_module(config_flow)


def _new_flow():
    _registered_unique_ids.clear()
    return config_flow.MqttMediaPlayerConfigFlow()


def test_user_step_shows_a_form_then_creates_the_hub_entry():
    flow = _new_flow()

    form = asyncio.run(flow.async_step_user(None))
    assert form == {"type": "form", "step_id": "user"}

    entry = asyncio.run(flow.async_step_user({}))
    assert entry["type"] == "create_entry"
    assert entry["title"] == config_flow.HUB_TITLE
    assert entry["data"] == {}
    assert flow._unique_id == config_flow.DOMAIN


def test_user_step_aborts_when_the_hub_already_exists():
    asyncio.run(_new_flow().async_step_user({}))

    second = config_flow.MqttMediaPlayerConfigFlow()
    try:
        asyncio.run(second.async_step_user({}))
    except _AbortFlow:
        return
    raise AssertionError("adding the hub twice must abort")


def test_import_step_creates_the_same_hub_entry():
    entry = asyncio.run(_new_flow().async_step_import(None))

    assert entry["type"] == "create_entry"
    assert entry["title"] == config_flow.HUB_TITLE
    assert entry["data"] == {}


def test_mqtt_step_creates_a_device_entry():
    flow = _new_flow()
    info = {
        "name": "projecteur_chambre_3e9b",
        "discovery_topic": "homeassistant/media_player/projecteur_chambre_3e9b/config",
        "discovery_data": {"name": "Projecteur Chambre"},
    }

    entry = asyncio.run(flow.async_step_mqtt(info))

    assert entry["type"] == "create_entry"
    assert entry["title"] == "projecteur_chambre_3e9b"
    assert entry["data"] == info


def test_mqtt_step_without_discovery_info_aborts():
    result = asyncio.run(_new_flow().async_step_mqtt(None))

    assert result == {"type": "abort", "reason": "no_discovery_info"}
