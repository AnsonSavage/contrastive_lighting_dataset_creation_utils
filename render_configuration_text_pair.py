"""Given a scene file, set up environment lighting and text description pairs for rendering.
"""
import bpy
from render_manager import HDRIManager, RenderManager

class RenderConfigurationTextPair:
    def __init__(self, environment_light_path: str, text_description: str, strength: float = 1.0, rotation: float = 0.0):
        self.environment_light_path = environment_light_path
        self.text_description = text_description
        self.strength = strength
        self.rotation = rotation

environment_light_path_and_text_description = [
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\overcast.exr",
        text_description='overcast outdoor lighting with some sun shining through the clouds',
        strength=4.0,
        rotation=-109.0
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\studio_small_08_4k.exr",
        text_description='three point studio lighting setup'
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\qwantani_dusk_2_puresky_4k.exr",
        text_description='beautiful, purple dusk lighting',
        rotation=-125.0
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\qwantani_sunset_4k.exr",
        text_description='low sunset lighting',
        rotation=-125.0
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\lonely_road_afternoon_4k.exr",
        text_description='bright afternoon outdoor lighting',
        rotation=165.0
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\satara_night_4k.exr",
        text_description='dark nighttime outdoor lighting with some artificial lights in the distance'
    ),
]


hdri_manager = HDRIManager()
render_manager = RenderManager()
for i, config in enumerate(environment_light_path_and_text_description):
    text_file_name = str(i).zfill(3) + ".txt"
    image_file_name = str(i).zfill(3) + ".png"
    with open(fr"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\{text_file_name}", "w") as f:
        f.write(config.text_description)

    hdri_manager.set_hdri(config.environment_light_path, strength=config.strength, rotation_degrees=config.rotation)
    render_manager.set_render_settings(
        output_path=fr"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\{image_file_name}",
        resolution=(1024, 1024),
        samples=512,
    )
    render_manager.render()