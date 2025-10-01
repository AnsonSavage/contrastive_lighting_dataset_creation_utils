from __future__ import annotations
from enum import auto
from dataclasses import dataclass
from .attribute import VariantAttribute
import os
import json
import argparse

from .attribute import EnumAttribute

class LightSize(EnumAttribute):
    SMALL = auto()
    MEDIUM = auto()
    LARGE = auto()

class LightDirection(EnumAttribute):
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

class LightIntensity(EnumAttribute):
    """ Size and distance-independent intensity """
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()

class LightColor(EnumAttribute):
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

class TimeOfDay(EnumAttribute):
    SUNRISE_SUNSET = auto()
    MORNING_AFTERNOON = auto()
    MIDDAY = auto()
    NIGHT = auto()
class IndoorOutdoor(EnumAttribute):
    INDOOR = auto()
    OUTDOOR = auto()
class NaturalArtificial(EnumAttribute):
    NATURAL = auto()
    ARTIFICIAL = auto()
class ContrastLevel(EnumAttribute):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()

required_enums_outdoor = set([IndoorOutdoor, NaturalArtificial, TimeOfDay, ContrastLevel])
required_enums_indoor = set([IndoorOutdoor, NaturalArtificial, ContrastLevel]) # If you're indoor, you don't need time of day

category_to_enum_map = {
    'outdoor': IndoorOutdoor.OUTDOOR,
    'natural light': NaturalArtificial.NATURAL,
    'sunrise-sunset': TimeOfDay.SUNRISE_SUNSET,
    'low contrast': ContrastLevel.LOW,
    'indoor': IndoorOutdoor.INDOOR,
    'artificial light': NaturalArtificial.ARTIFICIAL, # NOTE, some are tagged with both natural and artificial light... Do we want an override?
    'morning-afternoon': TimeOfDay.MORNING_AFTERNOON,
    'high contrast': ContrastLevel.HIGH,
    'midday': TimeOfDay.MIDDAY,
    'medium contrast': ContrastLevel.MEDIUM,
    'night': TimeOfDay.NIGHT
}

@dataclass
class HDRIName(LightSourceAttribute):
    """ Properties of the HDRI useful for contrastive image-image traingin"""
    name: str
    z_rotation_offset_from_camera: float

@dataclass
class HDRIProperties(LightSourceAttribute):
    """ Properties of the HDRI useful for text description generation """
    time_of_day: TimeOfDay | None
    indoor_outdoor: IndoorOutdoor
    natural_artificial: NaturalArtificial
    contrast_level: ContrastLevel

@dataclass
class VirtualLight(LightSourceAttribute):
    light_size: LightSize
    light_direction: LightDirection
    light_intensity: LightIntensity
    light_color: LightColor

    @classmethod
    def sample_value(cls, rng):
        return cls(
            light_size=LightSize.sample_value(rng),
            light_direction=LightDirection.sample_value(rng),
            light_intensity=LightIntensity.sample_value(rng),
            light_color=BlackbodyLightColor.sample_value(rng) # TODO: currently hardcoded to be blackbody
        )

class KeyLight(VirtualLight):
    pass
class FillLight(VirtualLight):
    pass
class RimLight(VirtualLight):
    pass

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
        my_properties = [category_to_enum_map[category] for category in categories if category in category_to_enum_map]
        # ensure we have all the required enums represented
        if IndoorOutdoor.INDOOR in [prop for prop in my_properties]:
            assert required_enums_indoor.issubset(set(type(prop) for prop in my_properties)), f"Missing required enums in {folder}: {required_enums_indoor - set(type(prop) for prop in my_properties)}"
        else:
            assert required_enums_outdoor.issubset(set(type(prop) for prop in my_properties)), f"Missing required enums in {folder}: {required_enums_outdoor - set(type(prop) for prop in my_properties)}"