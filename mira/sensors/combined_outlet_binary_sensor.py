"""Combined outlet binary sensor for Mira Soak Station devices.

This module provides a binary sensor that indicates if any outlet is running.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass


class SoakStationCombinedOutletBinarySensor(BinarySensorEntity):
    """Binary sensor representing the combined state of all outlets.
    
    This sensor is ON when at least one outlet is running, and OFF when
    all outlets are stopped. It provides a convenient way to check if
    any water flow is active on the device.
    
    Attributes:
        hass: Home Assistant instance
        _data: Device data model
        _meta: Device metadata
        _address: Device MAC address
        _device_name: User-friendly device name
    """

    def __init__(self, hass, data, meta, device_name, address):
        """Initialize the combined outlet binary sensor.
        
        Args:
            hass: Home Assistant instance
            data: Device data model
            meta: Device metadata
            device_name: User-friendly device name
            address: Device MAC address
        """
        # Store instance variables
        self.hass = hass
        self._data = data
        self._meta = meta
        self._address = address
        self._device_name = device_name

        # Configure entity attributes
        self._attr_name = f"Any Outlet Running ({device_name})"
        self._attr_unique_id = f"soakstation_any_outlet_{address.replace(':', '')}"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_icon = "mdi:water"
        self._attr_is_on = None
        self._attr_device_info = self._meta.get_device_info()

        # Subscribe to data model updates
        self._data.subscribe(self._update_from_model)

    def _update_from_model(self):
        """Update sensor state from the device data model.
        
        The sensor is ON if either outlet 1 or outlet 2 is running.
        """
        # Check if any outlet is running
        outlet_1_running = self._data.outlet_1_on or False
        outlet_2_running = self._data.outlet_2_on or False
        new_state = outlet_1_running or outlet_2_running

        # Update HA state if changed
        if self._attr_is_on != new_state:
            self._attr_is_on = new_state
            self.async_write_ha_state()

    async def async_update(self):
        """Update sensor state when Home Assistant polls.
        
        This method is called when Home Assistant explicitly polls the sensor.
        It delegates to _update_from_model to maintain consistent state handling.
        """
        self._update_from_model()
