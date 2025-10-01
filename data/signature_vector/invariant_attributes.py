from data.signature_vector.data_getters import OutdoorSceneData
from .attribute import InvariantAttribute
from dataclasses import dataclass
import random

@dataclass
class SceneID(InvariantAttribute):
    scene_id: str
    @classmethod
    def sample_value(cls, rng: random.Random) -> 'SceneID':
        available_scenes = OutdoorSceneData().get_available_scene_ids()
        selected_scene = rng.choice(available_scenes)
        return cls(scene_id=selected_scene)

@dataclass
class CameraSeed(InvariantAttribute):
    seed: int  # TODO: do we want to include any information here about whether it's a default, custom, or procedural camera?
    @classmethod
    def sample_value(cls, rng: random.Random) -> 'CameraSeed': # TODO: look into de-duping this with ContentSeed
        seed = rng.randint(0, int(1e6))
        return cls(seed=seed)

@dataclass
class ContentSeed(InvariantAttribute):
    seed: int  # TODO: do we include a material seed here, or elsewhere? Or will it be necessary?
    @classmethod
    def sample_value(cls, rng: random.Random) -> 'ContentSeed':
        seed = rng.randint(0, int(1e6))
        return cls(seed=seed)