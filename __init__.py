import logging
from datetime import timedelta

from bleak.exc import BleakError, BleakCharacteristicNotFoundError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .mira.helpers.connection import Connection
from .mira.helpers.data_model import SoakStationData, SoakStationMetadata
from .mira.helpers.notifications import Notifications


logger = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry):
    logger.debug("Setting up entry for device")
    device_address = config_entry.data["device_address"]
    client_id = config_entry.data["client_id"]
    client_slot = config_entry.data["client_slot"]
    logger.info(f"Setting up SoakStation device at {device_address} (client_id: {client_id}, client_slot: {client_slot})")

    connection = Connection(hass, device_address, client_id, client_slot)
    
    try:
        logger.debug("Connecting to device")
        await connection.connect()
    except Exception as e:
        logger.error(f"Failed to connect to device at {device_address}: {e}")
        raise ConfigEntryNotReady(f"Unable to connect to device: {e}") from e

    # Build the metadata wrapper and initialise it
    metadata = SoakStationMetadata()
    
    try:
        logger.debug("Getting device info")
        info = await connection.get_device_info()
        info['device_address'] = device_address
        metadata.update_device_identity(**info)
        logger.debug(f"Updated device metadata with info: {info}")
    except BleakCharacteristicNotFoundError as e:
        logger.error(f"Device characteristics not found. The device may not be fully connected or compatible: {e}")
        await connection.disconnect()
        raise ConfigEntryNotReady(f"Device characteristics not available: {e}") from e
    except BleakError as e:
        logger.error(f"Bluetooth error while getting device info: {e}")
        await connection.disconnect()
        raise ConfigEntryNotReady(f"Bluetooth error: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error getting device info: {e}")
        await connection.disconnect()
        raise ConfigEntryNotReady(f"Failed to get device info: {e}") from e

    # Build the data wrapper
    data_model = SoakStationData()
    logger.debug("Created data model")

    # Subscribe
    notifications = Notifications(model=data_model, metadata=metadata)
    connection.subscribe(notifications)
    logger.debug("Subscribed notifications handler")

    # Start requesting info
    try:
        logger.debug("Requesting technical info")
        await connection.request_technical_info()
        await metadata.wait_for_technical_info()
        logger.debug("Technical info received")

        logger.debug("Requesting initial device state")
        await connection.request_device_state()
    except Exception as e:
        logger.warning(f"Failed to get initial device state (will retry in polling): {e}")

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "connection": connection,
        "data": data_model,
        "metadata": metadata,
    }
    logger.debug("Stored device data in hass.data")

    # Set up periodic polling every 20 seconds
    async def poll_device_state(now):
        """Poll device state periodically with error handling and reconnection logic."""
        logger.debug("Polling device state")
        
        # Check if client is still connected
        if not connection.is_connected():
            logger.warning("Device not connected, attempting reconnection")
            try:
                await connection.reconnect()
                logger.info("Reconnection successful")
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                return
        
        try:
            await connection.request_device_state()
            logger.debug("Successfully polled device state")
        except BleakCharacteristicNotFoundError as e:
            logger.warning(f"Characteristic not found during polling: {e}")
            # Try reconnecting on characteristic errors
            try:
                logger.info("Attempting reconnection due to characteristic error")
                await connection.reconnect()
                await connection.request_device_state()
                logger.info("Reconnection and polling successful")
            except Exception as reconnect_error:
                logger.error(f"Reconnection attempt failed: {reconnect_error}")
        except BleakError as e:
            logger.warning(f"BLE error during polling: {e}")
            # Try reconnecting on BLE errors
            try:
                logger.info("Attempting reconnection due to BLE error")
                await connection.reconnect()
                await connection.request_device_state()
                logger.info("Reconnection and polling successful")
            except Exception as reconnect_error:
                logger.error(f"Reconnection attempt failed: {reconnect_error}")
        except Exception as e:
            logger.error(f"Unexpected error polling device state: {e}")

    logger.info("Setting up periodic polling every 20 seconds")
    async_track_time_interval(hass, poll_device_state, timedelta(seconds=20))

    logger.debug("Setting up platform entries")
    await hass.config_entries.async_forward_entry_setups(config_entry, ["binary_sensor", "sensor", "switch"])
    return True

async def async_unload_entry(hass, config_entry):
    logger.debug("Unloading entry")
    unload_bin = await hass.config_entries.async_forward_entry_unload(config_entry, "binary_sensor")
    unload_sens = await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    unload_sq = await hass.config_entries.async_forward_entry_unload(config_entry, "switch")
    logger.debug(f"Unloaded platforms - binary_sensor: {unload_bin}, sensor: {unload_sens}, switch: {unload_sq}")

    connection = hass.data[DOMAIN][config_entry.entry_id]["connection"]
    logger.debug("Disconnecting from device")
    await connection.disconnect()

    hass.data[DOMAIN].pop(config_entry.entry_id)
    logger.debug("Removed device data from hass.data")
    return unload_bin and unload_sens
