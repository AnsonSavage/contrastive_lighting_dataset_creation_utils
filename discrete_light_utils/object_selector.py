import os
import random
import bpy
from .object_loader import ObjectLoader
from utils.bbox_utils import get_bbox_extrema

class ObjectSelector:
    def __init__(self, directory: str, object_loader: ObjectLoader, min_height: float = 0.5, max_file_size_mb: float = 50.0):
        self.min_height = min_height
        self.max_file_size_mb = max_file_size_mb
        self.directory = directory
        self.supported_extensions = ('.glb', '.gltf', '.fbx')
        self.all_files = self._get_all_files()
        self.invalid_files = set()
        self.object_loader = object_loader

    def _get_all_files(self):
        if not os.path.isdir(self.directory):
            raise ValueError(f"Directory {self.directory} does not exist.")
        return [f for f in os.listdir(self.directory) if f.lower().endswith(self.supported_extensions) and os.path.getsize(os.path.join(self.directory, f)) <= self.max_file_size_mb * 1024 * 1024]

    def get_valid_files(self):
        return list(set(self.all_files) - self.invalid_files)

    def load_object(self, max_attempts: int = 50) -> bpy.types.Object:
        """
        Loads and validates a random object from the directory.
        Marks invalid objects and retries until a valid one is found.
        """
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            valid_files = self.get_valid_files()
            if not valid_files:
                raise RuntimeError("No valid files available to load.")

            candidate_filename = random.choice(valid_files)
            candidate_filepath = os.path.join(self.directory, candidate_filename)
            
            # Import the object(s)
            imported_objects = self.object_loader.import_object(candidate_filepath)
            
            # Preprocess (merges, cleans up, returns single object or None)
            candidate_object = self.object_loader.preprocess_objects(imported_objects)
            
            if candidate_object and self.selected_object_validation(candidate_object):
                return candidate_object
            
            print(f"Object '{candidate_filename}' failed validation. Marking as invalid and retrying.", flush=True)
            
            # If we have a candidate object (validation failed), remove it.
            # If candidate_object is None (preprocess failed), it cleaned itself up.
            if candidate_object:
                bpy.data.objects.remove(candidate_object, do_unlink=True)
                
            self.invalid_files.add(candidate_filename)
        
        raise RuntimeError(f"Failed to find a valid object after {max_attempts} attempts.")
            
    def selected_object_validation(self, obj: bpy.types.Object) -> bool:
        """
        Validates the selected object
        """
        return self.is_sufficiently_tall(obj) and not self.is_emissive(obj)  # Add more validation checks as needed

    def is_sufficiently_tall(self, obj: bpy.types.Object) -> bool:
        """
        Checks if the object's bounding box height is above a certain threshold (after object has been scaled, of course)
        """
        if not obj:
            return False
        
        min_bound, max_bound = get_bbox_extrema(obj)
        height = max_bound.z - min_bound.z
        
        passed = height >= self.min_height
        if not passed:
            print(f"Object '{obj.name}' height {height:.2f} is below minimum required height {self.min_height}.", flush=True)
        return passed

    def is_emissive(self, obj: bpy.types.Object) -> bool:
        """
        Checks if the object has any emissive materials.
        Returns True if any material slot is emissive.
        """
        if not obj or not obj.material_slots:
            return False

        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.use_nodes:
                is_emissive = False
                if not mat.node_tree:
                    continue
                    
                for node in mat.node_tree.nodes:
                    strength_input = None
                    color_input = None

                    # --- Case 1: Principled BSDF Shader ---
                    if node.type == 'BSDF_PRINCIPLED':
                        strength_input = node.inputs.get('Emission Strength') or node.inputs.get('Emission')
                        color_input = node.inputs.get('Emission') or node.inputs.get('Emission Color')

                    # --- Case 2: Emission Shader ---
                    elif node.type == 'EMISSION':
                        strength_input = node.inputs.get('Strength')
                        color_input = node.inputs.get('Color')

                    # --- Process the found node ---
                    if strength_input and color_input:
                        has_strength = False
                        if strength_input.is_linked:
                            has_strength = True
                        else:
                            # Handle case where strength_input might be a Color (older Blender versions)
                            val = strength_input.default_value
                            if hasattr(val, '__len__'):
                                # If it's a color, we assume strength is effectively present/1
                                # The color check will determine if it's actually emissive
                                has_strength = True
                            else:
                                has_strength = val > 0

                        is_not_black = False
                        if color_input.is_linked:
                            is_not_black = True
                        else:
                            val = color_input.default_value
                            # default_value is usually RGBA, so take first 3
                            if hasattr(val, '__len__') and len(val) >= 3:
                                is_not_black = any(val[:3])
                            else:
                                # Fallback if somehow it's a float
                                is_not_black = val > 0

                        if has_strength and is_not_black:
                            is_emissive = True
                            break
                
                if is_emissive:
                    return True
        
        return False
