import bpy
import random

class MaterialSelector:
    """" This class is in charge of selecting materials from a pre-defined library. """
    def __init__(self, path_to_material_library_blend: str, seed: int):
        self.rng = self.set_seed(seed)
        # Load the material library blend file
        with bpy.data.libraries.load(path_to_material_library_blend) as (data_from, data_to):
            # Assume all materials in the library are to be loaded
            data_to.materials = data_from.materials
        
        # Store loaded materials
        self.materials = list(data_to.materials)
    
    def select_material(self):
        """ Select a random material from the loaded library. """
        if not self.materials:
            raise ValueError("No materials loaded in the MaterialSelector.")
        return self.rng.choice(self.materials)
    
    def set_seed(self, seed: int) -> random.Random:
        """ Set the seed for random operations, if any. """
        self.rng = random.Random(seed)
        return self.rng

class MaterialManager:
    """ This class is responsible for methods related to assigning a material to an object. """
    def __init__(self):
        for obj in bpy.data.objects:
            # If object is a mesh and it doesn't have a UV map, create one
            if obj.type == 'MESH' and not obj.data.uv_layers:
                self.auto_unwrap(obj)

    def auto_unwrap(self, obj, method='SMART', island_margin: float = 0.03):
        """ Unwrap the given object for texture mapping. """
        bpy.ops.object.select_all(action='DESELECT')
                
        # Set as active and selected
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        
        # Apply scale to ensure UVs are not stretched
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Switch to Edit Mode (Required for UV operators)
        bpy.ops.object.mode_set(mode='EDIT')
        
        # Select all faces (Required to unwrap them)
        bpy.ops.mesh.select_all(action='SELECT')
        
        if method == 'SMART':
            # Run Smart UV Project
            # angle_limit: 66.0 is standard default
            # island_margin: Space between UV islands to prevent texture bleed
            bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=island_margin)
        elif method == 'CUBE':
            # Cube Projection - often better for boxy objects or architectural elements
            bpy.ops.uv.cube_project(cube_size=1.0, correct_aspect=True)
        
        # Switch back to Object Mode
        bpy.ops.object.mode_set(mode='OBJECT')

    def assign_material(self, obj, material):
        """ Assign the given material to the object. """
        if obj.data.materials:
            # Assign to first material slot
            obj.data.materials[0] = material
        else:
            # No slots
            obj.data.materials.append(material)
    
    def redo_uvs(self, objects: list, method: str = 'SMART', seed: int = None):
        """ Re-unwrap UVs for a list of objects using a specified method. 
        If method='RANDOM', randomly choose between SMART and CUBE projection.
        """
        if seed is not None:
            rng = random.Random(seed)
            for obj in objects:
                if obj.type == 'MESH':
                    chosen_method = rng.choice(['SMART', 'CUBE']) if method == 'RANDOM' else method
                    self.auto_unwrap(obj, method=chosen_method)
        else:
            for obj in objects:
                if obj.type == 'MESH':
                    chosen_method = random.choice(['SMART', 'CUBE']) if method == 'RANDOM' else method
                    self.auto_unwrap(obj, method=chosen_method)