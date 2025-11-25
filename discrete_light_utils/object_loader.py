import bpy
from mathutils import Vector


class ObjectLoader:
    def import_object(self, path_to_object: str) -> bpy.types.Object:
        """Loads a glb/fbx model into the scene and returns the active object."""
        # Deselect all objects first to identify the new ones
        bpy.ops.object.select_all(action='DESELECT')

        if path_to_object.endswith(".glb") or path_to_object.endswith(".gltf"):
            bpy.ops.import_scene.gltf(filepath=path_to_object, merge_vertices=True)
        elif path_to_object.endswith(".fbx"):
            bpy.ops.import_scene.fbx(filepath=path_to_object)
        else:
            raise ValueError(f"Unsupported file type: {path_to_object}")
        
        # The imported objects are selected. Get the active one.
        selected_objects = bpy.context.selected_objects
        if not selected_objects:
            print("Warning: No objects were imported.")
            return None
            
        active_obj = bpy.context.view_layer.objects.active
        if not active_obj and selected_objects:
            active_obj = selected_objects[0]
            bpy.context.view_layer.objects.active = active_obj
            
        return active_obj
    
    def set_object_origin(self, obj: bpy.types.Object) -> None:
        """
        Sets the object origin such that x and y are the center of the bounding box 
        and z is the min of the bounding box.
        """
        if not obj:
            return

        # Ensure the object is active and selected
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        
        # Force update to ensure bounding box is correct
        bpy.context.view_layer.update()
        
        # Calculate world space bounding box corners
        bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        
        min_x = min([v.x for v in bbox_corners])
        max_x = max([v.x for v in bbox_corners])
        min_y = min([v.y for v in bbox_corners])
        max_y = max([v.y for v in bbox_corners])
        min_z = min([v.z for v in bbox_corners])
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        bottom_z = min_z
        
        # Use the 3D cursor to set the origin
        saved_cursor_loc = bpy.context.scene.cursor.location.copy()
        
        bpy.context.scene.cursor.location = Vector((center_x, center_y, bottom_z))
        
        # Set origin to cursor
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        
        # Restore cursor
        bpy.context.scene.cursor.location = saved_cursor_loc

    def preprocess_object(self, imported_objects: list) -> bpy.types.Object:
        """
        Merges all imported mesh objects into a single object, removes non-mesh objects
        (empties, armatures, etc.), scales to fit 1m box, and sets the origin.
        Returns the final merged object, or None if no mesh objects were provided.
        """
        if not imported_objects:
            return None

        # Filter to only mesh objects
        mesh_objects = [obj for obj in imported_objects if obj.type == 'MESH']
        non_mesh_objects = [obj for obj in imported_objects if obj.type != 'MESH']

        if not mesh_objects:
            print("Warning: No mesh objects to preprocess.")
            # Still clean up non-mesh objects
            for obj in non_mesh_objects:
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception:
                    pass
            return None

        # 1. Clear parenting on mesh objects (keep transforms) BEFORE deleting parents
        for obj in mesh_objects:
            if obj.parent:
                # Store world matrix before clearing parent
                world_matrix = obj.matrix_world.copy()
                obj.parent = None
                obj.matrix_world = world_matrix

        # 2. Apply all transforms (Location, Rotation, Scale) to bake them into the mesh
        bpy.ops.object.select_all(action='DESELECT')
        for obj in mesh_objects:
            obj.select_set(True)
        
        if mesh_objects:
            bpy.context.view_layer.objects.active = mesh_objects[0]
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # 3. Remove all non-mesh objects (empties, armatures, etc.)
        for obj in non_mesh_objects:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass

        # 4. Join all selected mesh objects into one
        # (Objects are already selected from step 2)
        if mesh_objects:
            bpy.context.view_layer.objects.active = mesh_objects[0]

        if len(mesh_objects) > 1:
            bpy.ops.object.join()

        # The active object is now the merged result
        merged_obj = bpy.context.view_layer.objects.active

        # Scale the object to fit within a 1m x 1m x 1m bounding box (maintaining aspect ratio)
        self.scale_to_fit(merged_obj, size_of_max_dim=2.0)

        # Set the origin
        self.set_object_origin(merged_obj)

        return merged_obj

    def scale_to_fit(self, obj: bpy.types.Object, size_of_max_dim: float = 2.0) -> None:
        """
        Scales the object uniformly so that its largest dimension fits within max_size,
        maintaining aspect ratio.
        """
        if not obj:
            return

        # Force update to ensure bounding box is correct
        bpy.context.view_layer.update()

        # Calculate world space bounding box corners
        bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]

        min_x = min(v.x for v in bbox_corners)
        max_x = max(v.x for v in bbox_corners)
        min_y = min(v.y for v in bbox_corners)
        max_y = max(v.y for v in bbox_corners)
        min_z = min(v.z for v in bbox_corners)
        max_z = max(v.z for v in bbox_corners)

        size_x = max_x - min_x
        size_y = max_y - min_y
        size_z = max_z - min_z

        largest_dim = max(size_x, size_y, size_z)

        assert largest_dim > 0, "Object has zero or negative dimensions, cannot scale."

        scale_factor = size_of_max_dim / largest_dim

        # Apply uniform scale
        obj.scale *= scale_factor

        # Apply the scale so it becomes part of the mesh data
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
