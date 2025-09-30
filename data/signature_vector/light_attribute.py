from enum import Enum, auto
from dataclasses import dataclass
from .attribute import VariantAttribute
import os
import json
import argparse

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
    NIGHT = auto()
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

required_enums_outdoor = set([IndoorOutdoor, NaturalArtificial, TimeOfDay, ContrastLevel])
required_enums_indoor = set([IndoorOutdoor, NaturalArtificial, ContrastLevel]) # If you're indoor, you don't need time of day

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
    'medium contrast': ContrastLevel.MEDIUM,
    'night': TimeOfDay.NIGHT
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
import json
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List folders in an HDRI directory.")
    parser.add_argument("hdri_directory", type=str, help="Path to the HDRI directory")
    args = parser.parse_args()
    hdri_directory = args.hdri_directory
    for folder in os.listdir(hdri_directory):
        if not os.path.isdir(os.path.join(hdri_directory, folder)):
            continue
        print(folder)
        json_path = os.path.join(hdri_directory, folder, f"{folder}_asset_metadata.json")
        categories = json.load(open(json_path))['info']['categories']
        my_properties = [category_to_enum_maper[category] for category in categories if category in category_to_enum_maper]
        # ensure we have all the required enums represented
        if IndoorOutdoor.INDOOR in [prop for prop in my_properties]:
            assert required_enums_indoor.issubset(set(type(prop) for prop in my_properties)), f"Missing required enums in {folder}: {required_enums_indoor - set(type(prop) for prop in my_properties)}"
        else:
            assert required_enums_outdoor.issubset(set(type(prop) for prop in my_properties)), f"Missing required enums in {folder}: {required_enums_outdoor - set(type(prop) for prop in my_properties)}"