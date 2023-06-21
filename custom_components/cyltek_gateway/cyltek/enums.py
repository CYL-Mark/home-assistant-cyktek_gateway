from enum import Enum, IntEnum

"""Enum backports from standard lib."""
from enum import Enum
from typing import Any, TypeVar

_StrEnumSelfT = TypeVar("_StrEnumSelfT", bound="StrEnum")


class StrEnum(str, Enum):
    """Partial backport of Python 3.11's StrEnum for our basic use cases."""

    def __new__(
        cls: type[_StrEnumSelfT], value: str, *args: Any, **kwargs: Any
    ) -> _StrEnumSelfT:
        """Create a new StrEnum instance."""
        if not isinstance(value, str):
            raise TypeError(f"{value!r} is not a string")
        return super().__new__(cls, value, *args, **kwargs)

    def __str__(self) -> str:
        """Return self.value."""
        return str(self.value)

    @staticmethod
    def _generate_next_value_(
        name: str, start: int, count: int, last_values: list[Any]
    ) -> Any:
        """
        Make `auto()` explicitly unsupported.
        We may revisit this when it's very clear that Python 3.11's
        `StrEnum.auto()` behavior will no longer change.
        """
        raise TypeError("auto() is not supported by this implementation")


class CronType(Enum):
    """The type of event in cron."""

    off = 0


class PowerMode(IntEnum):
    """Power mode of the light."""

    LAST = 0
    NORMAL = 1
    RGB = 2
    HSV = 3
    COLOR_FLOW = 4
    MOONLIGHT = 5


class CYLightType(Enum):
    """
    The bulb's type.

    This is either `White` (for monochrome bulbs), `Color` (for color bulbs), `WhiteTemp` (for white bulbs with
    configurable color temperature), `WhiteTempMood` for white bulbs with mood lighting (like the JIAOYUE 650 LED
    ceiling light), or `Unknown` if the properties have not been fetched yet.
    """

    Unknown = -1
    White = 0
    Color = 1
    WhiteTemp = 2
    WhiteTempMood = 3


class LightType(IntEnum):
    """Type of light to control."""
    Main = 0
    Ambient = 1

class SceneClass(IntEnum):
    """
    The scene class to use.

    The scene class (as named in Yeelight docs) specifies how the `Bulb.set_scene` method should act.

    | `COLOR` changes the light to the specified RGB color and brightness.
    | `HSV` changes the light to the specified HSV color and brightness.
    | `CT` changes the light to the specified color temperature.
    | `CF` starts a color flow.
    | `AUTO_DELAY_OFF` turns the light on and sets a timer to turn it back off after the given number of minutes.
    """

    COLOR = 0
    HSV = 1
    CT = 2
    CF = 3
    AUTO_DELAY_OFF = 4
