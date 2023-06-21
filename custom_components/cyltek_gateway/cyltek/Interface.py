from abc import ABC, abstractmethod

"""Interfaces for specific functions"""

class IBrightness(ABC):
    @abstractmethod
    def update_brightness(self):
        pass

    @abstractmethod
    def set_brightness(self, brightness):
        pass

    @property
    @abstractmethod
    def brightness(self):
        pass

class IPower(ABC):
    @abstractmethod
    def update_power(self):
        pass

    @abstractmethod
    def turn_on(self):
        pass

    @abstractmethod
    def turn_off(self):
        pass

    @property
    @abstractmethod
    def power(self):
        pass


class IMode(ABC):
    @abstractmethod
    def available_modes(self):
        pass

    @abstractmethod
    def update_mode(self):
        pass

    @abstractmethod
    def set_mode(self, mode):
        pass

    @property
    @abstractmethod
    def mode(self):
        pass


class IFanMode(ABC):
    @abstractmethod
    def available_fan_modes(self):
        pass

    @abstractmethod
    def update_fan_mode(self):
        pass

    @abstractmethod
    def set_fan_mode(self, mode):
        pass

    @property
    @abstractmethod
    def fan_mode(self):
        pass


class ISwingMode(ABC):
    @abstractmethod
    def available_swing_modes(self):
        pass

    @abstractmethod
    def update_swing_mode(self):
        pass

    @abstractmethod
    def set_swing_mode(self, mode):
        pass

    @property
    @abstractmethod
    def swing_mode(self):
        pass


class IHumidity(ABC):
    @abstractmethod
    def update_humidity(self):
        pass

    @property
    @abstractmethod
    def humidity(self):
        pass


class ITemperature(ABC):
    @abstractmethod
    def update_temperature(self):
        pass

    @property
    @abstractmethod
    def temperature(self):
        pass


class ITargetHumidity(ABC):
    @abstractmethod
    def update_target_humidity(self):
        pass

    @abstractmethod
    def set_target_humidity(self, humidity):
        pass

    @property
    @abstractmethod
    def max_target_humidity(self):
        pass

    @property
    @abstractmethod
    def min_target_humidity(self):
        pass

    @property
    @abstractmethod
    def target_humidity(self):
        pass


class ITargetTemperature(ABC):
    @abstractmethod
    def update_target_temperature(self):
        pass

    @abstractmethod
    def set_target_temperature(self, temperature):
        pass

    @property
    @abstractmethod
    def max_target_temperature(self):
        pass

    @property
    @abstractmethod
    def min_target_temperature(self):
        pass

    @property
    @abstractmethod
    def target_temperature(self):
        pass
