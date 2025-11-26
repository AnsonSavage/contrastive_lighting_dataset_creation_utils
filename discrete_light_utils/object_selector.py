import os
import random
import bpy

class ObjectSelector:
    def __init__(self, directory: str):
        self.directory = directory
        self.supported_extensions = ('.glb', '.gltf', '.fbx')
        self.all_files = self._get_all_files()
        self.invalid_files = set()

    def _get_all_files(self):
        if not os.path.isdir(self.directory):
            raise ValueError(f"Directory {self.directory} does not exist.")
        return [f for f in os.listdir(self.directory) if f.lower().endswith(self.supported_extensions)]

    def get_valid_files(self):
        return list(set(self.all_files) - self.invalid_files)

    def select_random_file(self):
        valid_files = self.get_valid_files()
        if not valid_files:
            return None
        return random.choice(valid_files)

    def mark_invalid(self, filename: str):
        self.invalid_files.add(filename)

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
