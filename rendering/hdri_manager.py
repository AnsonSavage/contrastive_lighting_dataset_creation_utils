import bpy
import math


class HDRIManager:
    """Manages HDRI environment texture setup in Blender's World settings."""
    
    def set_hdri(self, hdri_path: str, strength: float = 1.0, rotation_degrees: float = 0.0) -> None:
        """
        Set an HDRI environment texture in Blender's World settings.
        
        :param hdri_path: Full path to the HDRI image file
        :param strength: Strength/intensity of the HDRI lighting
        :param rotation_degrees: Z-axis rotation offset in degrees
        """
        # Clear existing world nodes
        bpy.context.scene.world.node_tree.nodes.clear()
        
        # Create new World output node
        world_output = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeOutputWorld')
        
        # Create Environment Texture node
        env_texture = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeTexEnvironment')
        
        # Set the image for the Environment Texture
        env_texture.image = bpy.data.images.load(str(hdri_path))
        
        # Create Background node
        background = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeBackground')

        # Create Mapping node
        mapping = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeMapping')
        mapping.vector_type = 'POINT'
        mapping.inputs['Rotation'].default_value[2] = math.radians(rotation_degrees)

        # Create texture coordinate node
        tex_coord = bpy.context.scene.world.node_tree.nodes.new(type='ShaderNodeTexCoord')
        
        # Link nodes
        links = bpy.context.scene.world.node_tree.links
        links.new(env_texture.outputs["Color"], background.inputs["Color"])
        links.new(background.outputs["Background"], world_output.inputs["Surface"])
        links.new(mapping.outputs["Vector"], env_texture.inputs["Vector"])
        links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
        
        background.inputs["Strength"].default_value = strength
