from .attribute import InvariantAttribute
from dataclasses import dataclass

@dataclass
class SceneID(InvariantAttribute):
    id: str

class CameraSeed(InvariantAttribute):
    seed: int # TODO: do we want to include any information here about whether it's a default, custom, or procedural camera?

class ContentSeed(InvariantAttribute):
    seed: int # TODO: do we include a material seed here, or elsewhere? Or will it be necessary?
