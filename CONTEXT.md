# MQTT Media Player

A Home Assistant custom integration (fork of `bkbilly/mqtt_media_player`) that turns MQTT topics into a `media_player` entity, discovered through MQTT.

## Language

**Media player state**:
The last values observed for a discovered player, independent of Home Assistant.
_Avoid_: state object, DTO

**Discovery config**:
The retained MQTT payload that creates and configures the `media_player` entity.
_Avoid_: registration, announcement

**Command**:
An action Home Assistant asks the player to perform (play, pause, volume, …).
_Avoid_: action, request
