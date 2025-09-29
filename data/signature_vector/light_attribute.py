from enum import Enum, auto
from dataclasses import dataclass
from data.signature_vector.attribute import VariantAttribute

class LightSize(Enum):
    SMALL = auto()
    MEDIUM = auto()
    LARGE = auto()

class LightDirection(Enum):
    BACK_RIGHT = auto()
    BACK_LEFT = auto()
    BACK = auto()
    RIGHT = auto()
    LEFT = auto()
    FRONT_RIGHT = auto()
    FRONT_LEFT = auto()
    FRONT = auto()
    TOP = auto()
    BOTTOM = auto()

class LightIntensity(Enum):
    """ Size and distance-independent intensity """
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()

class LightColor(Enum):
    pass
class BlackbodyLightColor(LightColor):
    WARM = auto()
    NEUTRAL = auto()
    COOL = auto()

class HueLightColor(LightColor):
    RED = auto()
    ORANGE = auto()
    YELLOW = auto()
    GREEN = auto()
    TEAL = auto()
    BLUE = auto()
    PURPLE = auto()
    PINK = auto()
    WHITE = auto()

class LightSourceAttribute(VariantAttribute):
    pass

class TimeOfDay(Enum):
    SUNRISE_SUNSET = auto()
    MORNING_AFTERNOON = auto()
    MIDDAY = auto()
class IndoorOutdoor(Enum):
    INDOOR = auto()
    OUTDOOR = auto()
class NaturalArtificial(Enum):
    NATURAL = auto()
    ARTIFICIAL = auto()
class ContrastLevel(Enum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()

category_to_enum_maper = {
    'outdoor': IndoorOutdoor.OUTDOOR,
    'natural light': NaturalArtificial.NATURAL,
    'sunrise-sunset': TimeOfDay.SUNRISE_SUNSET,
    'low contrast': ContrastLevel.LOW,
    'indoor': IndoorOutdoor.INDOOR,
    'artificial light': NaturalArtificial.ARTIFICIAL, # note, some are tagged with both natural and artificial light... Do we want an override?
    'morning-afternoon': TimeOfDay.MORNING_AFTERNOON,
    'high contrast': ContrastLevel.HIGH,
    'midday': TimeOfDay.MIDDAY,
}

class HDRI(LightSourceAttribute):
    pass
@dataclass
class VirtualLight(LightSourceAttribute):
    light_size: 'LightSize' = None
class KeyLight(VirtualLight):
    pass
class FillLight(VirtualLight):
    pass
class RimLight(VirtualLight):
    pass

import os
if __name__ == "__main__":
    for folder in os.listdir(r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils\dummy_data\hdri'):
        print(folder)