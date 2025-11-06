import os
import tempfile
import bpy

from .log import log


class RenderManager:
    """
    Core render manager that configures render settings and triggers the render.
    Compose this with a SceneManager which is responsible for scene setup.
    """
    def __init__(self):
        self.is_render_settings_configured = False

    @staticmethod
    def set_gpu():
        log("Attempting to configure GPU rendering...")
        try:
            bpy.context.scene.render.engine = "CYCLES"
            bpy.context.scene.cycles.device = "GPU"

            prefs = bpy.context.preferences.addons["cycles"].preferences

            # Try to set OPTIX
            try:
                prefs.compute_device_type = "OPTIX"
                prefs.get_devices() # This will error if 'OPTIX' is not a valid type
            except Exception:
                # If OPTIX fails, fall back to CUDA
                try:
                    prefs.compute_device_type = "CUDA"
                    prefs.get_devices()
                except Exception as e2:
                    log(f"Warning: Could not set OPTIX or CUDA: {e2}")

            log(f"Set compute backend to: {prefs.compute_device_type}")

            # Call get_devices() again to populate the list for the chosen backend
            prefs.get_devices()

            # Enable all devices (GPU and CPU)
            if not prefs.devices:
                raise Exception("No devices found for the selected backend.")

            log("Enabling devices...")
            for d in prefs.devices:
                d.use = True # Set device to be used
                log(f"Enabled: {d.name}, Type: {d.type}, Use: {d.use}")

        except Exception as e:
            log(f"Warning: Could not configure GPU rendering preferences: {e}")
            log("Will attempt to render with default scene settings.")
    
    def set_render_settings(
        self,
        output_path: str = os.path.join(tempfile.gettempdir(), "render.png"),
        resolution: tuple[int, int] = (384, 384),
        use_denoising: bool = True,
        use_denoising_gpu: bool = True,
        samples: int = 128,
        use_gpu_rendering: bool = True
    ) -> None:
        """Configure render settings for Cycles."""
        scene = bpy.context.scene
        scene.render.filepath = output_path
        scene.render.resolution_x = resolution[0]
        scene.render.resolution_y = resolution[1]
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGB'
        scene.render.resolution_percentage = 100
        scene.cycles.use_denoising = use_denoising
        scene.cycles.denoising_use_gpu = use_denoising_gpu
        scene.cycles.samples = samples
        if use_gpu_rendering:
            RenderManager.set_gpu()

        # Color management settings (AgX + defaults)
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'None'  # default contrast/look
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0
        try:
            scene.sequencer_colorspace_settings.name = 'sRGB'
        except Exception:
            pass
        self.is_render_settings_configured=True
    
    def render(self, output_path=None) -> str:
        """
        Main render entry point.
        
        :param output_path: Where to save the rendered image (use None to use the previous render settings)
        :return: Path to the rendered image
        """
        if not self.is_render_settings_configured:
            log("Warning: render settings have not been configured")

        scene = bpy.context.scene
        if output_path is not None:
            scene.render.filepath = output_path

        bpy.ops.render.render(write_still=True)
        log(f"Render complete: {scene.render.filepath}")
        return scene.render.filepath
