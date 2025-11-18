"""Number platform for Mira Soak Station devices.

This module handles the setup of number entities that control device settings
like temperature setpoint for the Mira Soak Station device.
"""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN


class SoakStationTemperatureNumber(NumberEntity):
    """Number entity for controlling the temperature setpoint.
    
    This entity allows users to set the target temperature for the outlets.
    When the temperature is changed, it updates the device with the new setpoint
    and current outlet states.
    
    Attributes:
        hass: Home Assistant instance
        _connection: Device connection handler
        _model: Device data model
        _metadata: Device metadata
    """

    def __init__(self, hass, connection, model, metadata):
        """Initialize the temperature number entity.
        
        Args:
            hass: Home Assistant instance
            connection: Device connection handler
            model: Device data model
            metadata: Device metadata
        """
        super().__init__()
        
        # Store instance variables
        self._hass = hass
        self._connection = connection
        self._model = model
        self._metadata = metadata
        
        # Configure entity attributes
        self._attr_name = f"Target Temperature ({metadata.name})"
        self._attr_unique_id = f"{metadata.device_address.replace(':', '')}_target_temperature"
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_mode = NumberMode.SLIDER
        self._attr_device_info = self._metadata.get_device_info()
        
        # Set temperature limits from device metadata (default to common shower temps if not available)
        self._attr_native_min_value = metadata.min_temperature if metadata.min_temperature else 20.0
        self._attr_native_max_value = metadata.max_temperature if metadata.max_temperature else 50.0
        self._attr_native_step = 0.5
        
        # Set initial value
        self._attr_native_value = model.target_temp if model.target_temp else 38.0
        
        # Subscribe to model updates
        self._model.subscribe(self._handle_model_update)

    def _handle_model_update(self):
        """Update number state from the device data model.
        
        Gets the current target temperature and updates Home Assistant
        if the value has changed.
        """
        new_value = self._model.target_temp
        
        # Also update min/max limits if metadata has been updated with device settings
        limits_changed = False
        if self._metadata.min_temperature and self._attr_native_min_value != self._metadata.min_temperature:
            self._attr_native_min_value = self._metadata.min_temperature
            limits_changed = True
        if self._metadata.max_temperature and self._attr_native_max_value != self._metadata.max_temperature:
            self._attr_native_max_value = self._metadata.max_temperature
            limits_changed = True
        
        # Update if value or limits changed
        if (new_value is not None and new_value != self._attr_native_value) or limits_changed:
            if new_value is not None:
                self._attr_native_value = new_value
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new target temperature.
        
        Updates the device with the new temperature setpoint while maintaining
        the current outlet states.
        
        Args:
            value: New temperature setpoint in Celsius
        """
        # Get current outlet states
        outlet_1_on = self._model.outlet_1_on or False
        outlet_2_on = self._model.outlet_2_on or False
        
        # Send command to device with new temperature
        await self._connection.control_outlets(outlet_1_on, outlet_2_on, temperature=value)
        
        # Update local state
        self._attr_native_value = value
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up number entities for the Mira Soak Station device.
    
    Args:
        hass: Home Assistant instance
        config_entry: Configuration entry containing device details
        async_add_entities: Callback to add entities to Home Assistant
    """
    # Get device data from hass storage
    data = hass.data[DOMAIN][config_entry.entry_id]
    connection = data["connection"]
    metadata = data["metadata"]
    model = data["data"]

    # Create temperature number entity
    numbers = [
        SoakStationTemperatureNumber(hass, connection, model, metadata),
    ]

    # Register number entities with Home Assistant
    async_add_entities(numbers)
