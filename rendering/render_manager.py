import os
import tempfile
import bpy
from aov_manager import configure_aovs

from .log import log


class RenderManager:
    """
    Core render manager that configures render settings and triggers the render.
    Compose this with a SceneManager which is responsible for scene setup.
    """
    def __init__(self):
        self.is_render_settings_configured = False
        self.bypass_compositing_nodes = False

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
        use_gpu_rendering: bool = True,
        bypass_compositing_nodes: bool = False,
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
        scene.cycles.use_persistent_data = True
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

        self.bypass_compositing_nodes = bypass_compositing_nodes
        self.is_render_settings_configured=True
    
    def set_aovs(self, aov_names: list[str], output_directory: str) -> None:
        """
        Configure Arbitrary Output Variables (AOVs) to be rendered.
        
        :param aov_names: List of AOV names to configure (e.g. 'metallic', 'albedo', 'roughness')
        :param output_directory: Directory where AOV outputs will be saved
        """
        configure_aovs(aov_names, output_directory)


    def render(self, output_path=None) -> str:
        """
        Main render entry point.
        
        :param output_path: Where to save the rendered image (use None to use the previous render settings)
        :return: Path to the rendered image
        """
        if not self.is_render_settings_configured:
            log("Warning: render settings have not been configured")
        
        if self.bypass_compositing_nodes:
            self._bypass_compositing_nodes()

        scene = bpy.context.scene
        if output_path is not None:
            scene.render.filepath = output_path

        bpy.ops.render.render(write_still=True)
        log(f"Render complete: {scene.render.filepath}")
        return scene.render.filepath
    
    def _bypass_compositing_nodes(self):
        """
        Finds the Render Layers and Composite nodes in the active scene's
        compositor by their node type and connects the 'Image' output
        of the Render Layers node to the 'Image' input of the Composite
        node. This bypasses any custom names.
        
        It removes any existing links to the Composite node's Image input.
        """
        
        # Get the active scene
        scene = bpy.context.scene
        
        # Ensure compositing nodes are enabled
        if not scene.use_nodes:
            log("Compositing nodes are not enabled for this scene.")
            return

        # Get the compositing node tree
        tree = scene.node_tree
        
        # Find nodes by type
        render_node = None
        composite_node = None

        for node in tree.nodes:
            if node.bl_idname == 'CompositorNodeRLayers':
                render_node = node
                break 
                
        for node in tree.nodes:
            if node.bl_idname == 'CompositorNodeComposite':
                composite_node = node
                break

        # Check if both nodes were found
        if not render_node:
            log("Could not find a 'Render Layers' node (CompositorNodeRLayers).")
            return
            
        if not composite_node:
            log("Could not find a 'Composite' node (CompositorNodeComposite).")
            return

        # Get the specific sockets
        try:
            render_output = render_node.outputs['Image']
            composite_input = composite_node.inputs['Image']
        except KeyError as e:
            log(f"Error finding socket: {e}. Nodes may be of unexpected types.")
            return

        # Remove any existing links connected to the Composite's 'Image' input
        for link in composite_input.links:
            tree.links.remove(link)
            
        # Create the new, direct link
        try:
            tree.links.new(render_output, composite_input)
            log("Successfully linked 'Render Layers' to 'Composite' by type.")
        except Exception as e:
            log(f"An error occurred while linking: {e}")
