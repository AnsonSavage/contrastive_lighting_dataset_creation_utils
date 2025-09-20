import bpy
import pathlib
import math # Imported for converting degrees to radians

class HDRIManager:
    """Responsible for managing the available HDRIs and setting them in the scene."""

    def __init__(self, hdri_directory: str, recursive: bool = True):
        self.available_hdris = self._get_available_hdris(hdri_directory, recursive)
    
    def _get_available_hdris(self, hdri_directory, recursive):
        """Returns a list of available HDRIs in the specified directory.
        
        :param hdri_directory: Path to the HDRI directory
        :param recursive: Whether to search subdirectories
        """
        hdri_directory = pathlib.Path(hdri_directory)
        # UPDATED: Only search for .exr and .hdr files
        allowed_suffixes = [".exr", ".hdr"]
        
        if recursive:
            hdris = [hdri for hdri in hdri_directory.rglob('*') if hdri.suffix.lower() in allowed_suffixes]
        else:
            hdris = [hdri for hdri in hdri_directory.iterdir() if hdri.suffix.lower() in allowed_suffixes]
        return hdris

    def set_hdri(self, hdri_path: str, strength: float = 1.0, rotation_z: float = 0.0): # TODO: test the rotation_z
        """
        Set an HDRI environment texture in Blender's World settings.
        
        :param hdri_path: Full path to the HDRI image file.
        :param strength: The brightness of the HDRI.
        :param rotation_z: The rotation of the HDRI on the Z-axis in degrees.
        """
        world = bpy.context.scene.world
        
        # Ensure the world has a node tree
        if world.use_nodes is False:
            world.use_nodes = True
        
        # Clear existing world nodes
        world.node_tree.nodes.clear()
        
        # Create the core nodes
        world_output = world.node_tree.nodes.new(type='ShaderNodeOutputWorld')
        background = world.node_tree.nodes.new(type='ShaderNodeBackground')
        env_texture = world.node_tree.nodes.new(type='ShaderNodeTexEnvironment')
        
        # --- NEW NODES FOR ROTATION ---
        # Create Texture Coordinate and Mapping nodes to control the HDRI's rotation
        tex_coord = world.node_tree.nodes.new(type='ShaderNodeTexCoord')
        mapping = world.node_tree.nodes.new(type='ShaderNodeMapping')
        
        # Load the HDRI image
        env_texture.image = bpy.data.images.load(str(hdri_path))
        
        # Set the strength of the HDRI
        background.inputs["Strength"].default_value = strength
        
        # Set the Z rotation on the Mapping node
        # The rotation value is a 3D vector (X, Y, Z) that expects radians
        mapping.inputs["Rotation"].default_value[2] = math.radians(rotation_z)

        # Link the nodes together
        links = world.node_tree.links
        links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], env_texture.inputs["Vector"])
        links.new(env_texture.outputs["Color"], background.inputs["Color"])
        links.new(background.outputs["Background"], world_output.inputs["Surface"])