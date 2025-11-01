"""Given a scene file, set up environment lighting and text description pairs for rendering.
"""
import bpy
from render_manager import HDRIManager, RenderManager

class RenderConfigurationTextPair:
    def __init__(self, environment_light_path: str, text_description: str):
        self.environment_light_path = environment_light_path
        self.text_description = text_description

environment_light_path_and_text_description = [
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\overcast.exr",
        text_description='overcast outdoor lighting with some sun shining through the clouds'
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\studio_small_08_4k.exr",
        text_description='three point studio lighting setup'
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\qwantani_dusk_2_puresky_4k.exr",
        text_description='beautiful, purple dusk lighting'
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\qwantani_sunset_4k.exr",
        text_description='low sunset lighting'
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\lonely_road_afternoon_4k.exr",
        text_description='bright afternoon outdoor lighting'
    ),
    RenderConfigurationTextPair(
        environment_light_path=r"C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\tests\olat\scenes\environment_lights\satara_night_4k.exr",
        text_description='dark nighttime outdoor lighting with some artificial lights in the distance'
    ),
]


hdri_manager = HDRIManager()
render_manager = RenderManager()
for config in environment_light_path_and_text_description:
    hdri_manager.set_hdri(config.environment_light_path)
    render_manager.set_render_settings(
        output_path=f"/path/to/output/{config.text_description.replace(' ', '_')}.png",
        resolution=(1024, 1024),
        samples=512,
    )
    render_manager.render()