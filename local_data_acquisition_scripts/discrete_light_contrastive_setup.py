import bpy
import random
import math
from mathutils import Vector, Matrix, Euler
import sys

import importlib
sys.path.append(r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils')
from camera_spawner import CameraSpawner
from utils.random_utils import get_random_point_on_surface
importlib.reload(sys.modules.get('camera_spawner'))
importlib.reload(sys.modules.get('utils.random_utils'))
import os
import glob
import argparse

class DiscreteLightGenerator:
    def __init__(self, collection_name="Generated_Lighting", seed=21):
        self.seed = seed
        self.collection_name = collection_name
        
        # Cone Angle (where 90.0 = Full Hemisphere)
        self.max_cone_angle = 70.0

        # Light Count
        self.min_lights = 1
        self.max_lights = 3

        # Distance / Size / Power
        self.min_dist = 2.5
        self.max_dist = 6.0
        self.min_size = 0.5
        self.max_size = 2.0
        self.min_power = 200.0
        self.max_power = 1000.0

        # Saturation
        self.saturation_min = 0.1
        self.saturation_max = 0.9

        # Per-instance RNG (so we don't mutate global random state)
        self.rng = random.Random(self.seed)

    def sample_cone(self, normal: Vector, theta_max_deg: float) -> Vector:
        """
        Generates a random unit vector within a cone defined by a normal and max angle.
        Uniformly distributed over the solid angle.
        """
        theta_max = math.radians(theta_max_deg)
        u = self.rng.random()
        v = self.rng.random()
        
        # Uniform distribution over the spherical cap
        cos_theta = (1 - u) + u * math.cos(theta_max)
        sin_theta = math.sqrt(1 - cos_theta * cos_theta)
        phi = 2 * math.pi * v
        
        # Local direction (cone axis is +Z)
        dir_local = Vector((sin_theta * math.cos(phi), sin_theta * math.sin(phi), cos_theta))
        
        # Build orthonormal basis from normal
        def basis_from_normal(n):
            n = n.normalized()
            # Handle the edge case where normal is close to Z-up
            if abs(n.z) < 0.999:
                t = n.cross(Vector((0,0,1))).normalized()
            else:
                t = n.cross(Vector((0,1,0))).normalized()
            b = n.cross(t)
            return Matrix((t, b, n)).transposed() # Transposed to align columns
        
        M = basis_from_normal(normal)
        return (M @ dir_local).normalized()

    def clear_previous_lights(self):
        if self.collection_name in bpy.data.collections:
            coll = bpy.data.collections[self.collection_name]
            objs_to_remove = [obj for obj in coll.objects]
            light_data_to_remove = {obj.data for obj in objs_to_remove if obj.data and obj.type == 'LIGHT'}
            
            for obj in objs_to_remove:
                bpy.data.objects.remove(obj, do_unlink=True)

            for light_data in light_data_to_remove:
                if light_data and light_data.users == 0:
                    bpy.data.lights.remove(light_data)

    @staticmethod
    def hsv_to_rgb(h, s, v):
        import colorsys
        return colorsys.hsv_to_rgb(h, s, v)

    def generate_lights(self, target_object, camera):
        if not target_object or not camera:
            print("Error: Select an object and ensure a camera exists.")
            return

        self.clear_previous_lights()

        # Create Collection
        if self.collection_name not in bpy.data.collections:
            light_collection = bpy.data.collections.new(self.collection_name)
            bpy.context.scene.collection.children.link(light_collection)
        else:
            light_collection = bpy.data.collections[self.collection_name]

        num_lights = self.rng.randint(self.min_lights, self.max_lights)

        cam_rot_mat = camera.matrix_world.to_quaternion().to_matrix()

        target_loc = target_object.location
        
        # We define the "Up" direction for the hemisphere.
        # Using Global Z (0,0,1) ensures we don't intersect the floor.
        # If you wanted the lights to come from the camera's direction, you would use:
        # cone_axis = active_cam.matrix_world.to_quaternion() @ Vector((0,0,-1))
        cone_axis = Vector((0, 0, 1)) 

        print(f"Generating {num_lights} lights in a {self.max_cone_angle} degree cone...")

        light_objs = []
        for i in range(num_lights):
            # 1. Random Props (use per-instance RNG)
            dist = self.rng.uniform(self.min_dist, self.max_dist)
            size = self.rng.uniform(self.min_size, self.max_size)
            power = self.rng.uniform(self.min_power, self.max_power)
            color_rgb = self.hsv_to_rgb(self.rng.random(), self.rng.uniform(self.saturation_min, self.saturation_max), 1.0)

            # 2. Calculate Position using sample_cone
            # This returns a unit vector pointing somewhere in the sky
            direction_vec = self.sample_cone(cone_axis, self.max_cone_angle)
            
            # Scale by distance
            local_vec = direction_vec * dist

            matrix_to_align_camera_with_y_axis = self.get_matrix_to_align_with_camera_looking_down_y_axis(camera)
            aligned_vec = matrix_to_align_camera_with_y_axis @ local_vec
            
            final_pos = target_loc + aligned_vec

            # 3. Create Light
            light_data = bpy.data.lights.new(name=f"GenLight_{self.seed}_{i}", type='AREA')
            light_obj = bpy.data.objects.new(name=f"GenLight_{self.seed}_{i}", object_data=light_data)
            
            light_collection.objects.link(light_obj)
            
            light_obj.location = final_pos
            light_data.energy = power
            light_data.color = color_rgb
            light_data.shape = 'SQUARE'
            light_data.size = size

            # 4. Point Light at Object
            direction = target_loc - light_obj.location
            light_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

            light_objs.append(light_obj)

        bpy.context.view_layer.update()
        self.post_check_light_visibility(light_objs, target_object)
        print("Done.")
    
    def get_matrix_to_align_with_camera_looking_down_y_axis(self, camera: bpy.types.Object) -> Matrix:
        # camera_rotation_inverted = camera.matrix_world.to_quaternion().to_matrix().inverted() # should also be able to use the transpose b/c it's an orthonormal matrix
        # matrix_to_align_camera_with_y_axis = Euler((math.pi/2, 0, 0), 'XYZ').to_matrix() @ camera_rotation_inverted
        # return matrix_to_align_camera_with_y_axis.inverted()
        # Simplifies to:
        camera_rotation = camera.matrix_world.to_quaternion().to_matrix()
        return camera_rotation @ (Euler((math.pi/2, 0, 0), 'XYZ').to_matrix().transposed())

    def set_seed(self, new_seed):
        self.seed = new_seed
        self.rng = random.Random(self.seed)

    def check_visibility(self, light_pos, target_obj):
        scene = bpy.context.scene
        depsgraph = bpy.context.evaluated_depsgraph_get()
        
        # 1. Check center
        target_center = target_obj.matrix_world.translation
        direction = target_center - light_pos
        dist = direction.length
        if dist < 1e-4: # If we're close, consider it visible
            return True
            
        success, location, normal, index, object, matrix = scene.ray_cast(depsgraph, light_pos, direction.normalized())
        
        if success and object == target_obj:
            return True
            
        # 2. Check a subset of vertices to see if any of them are visible from the light
        if target_obj.type == 'MESH':
            mw = target_obj.matrix_world
            mesh = target_obj.data
            vertices = mesh.vertices
            
            step = max(1, len(vertices) // 50) 
            
            for i in range(0, len(vertices), step):
                v = vertices[i]
                v_world = mw @ v.co
                direction = v_world - light_pos
                dist = direction.length
                
                if dist < 1e-6:
                    continue
                    
                success, location, normal, index, object, matrix = scene.ray_cast(depsgraph, light_pos, direction.normalized(), distance=dist + 1.0)
                
                if success and object == target_obj:
                    return True
                    
        return False

    def post_check_light_visibility(self, light_objs, target_obj):
        visible_count = 0
        for light_obj in light_objs:
            pos = light_obj.location
            if self.check_visibility(pos, target_obj):
                print(f"Light {light_obj.name} is visible to the target object.")
                visible_count += 1
            else:
                print(f"Light {light_obj.name} is NOT visible to the target object.")
        print(f"{visible_count}/{len(light_objs)} lights are visible to the target object.")

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
        self.scale_to_fit(merged_obj, max_size=1.0)

        # Set the origin
        self.set_object_origin(merged_obj)

        return merged_obj

    def scale_to_fit(self, obj: bpy.types.Object, max_size: float = 1.0) -> None:
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

        scale_factor = max_size / largest_dim

        # Apply uniform scale
        obj.scale *= scale_factor

        # Apply the scale so it becomes part of the mesh data
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    
def get_object_rotation_degrees (obj: bpy.types.Object, axis:str) -> float:
    assert axis.lower() in ('x', 'y', 'z'), "Axis must be 'x', 'y', or 'z'"
    return math.degrees(getattr(obj.rotation_euler, axis.lower()))

def place_empty_at_location(location: Vector, name: str = "Empty") -> bpy.types.Object:
    """Places an empty object at the specified location."""
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=location)
    empty_obj = bpy.context.active_object
    empty_obj.name = name
    return empty_obj


def clear_collection_objects(collection_name: str):
    """Remove all objects in the named collection (and their data if unused)."""
    if collection_name in bpy.data.collections:
        coll = bpy.data.collections[collection_name]
        objs_to_remove = [obj for obj in coll.objects]
        for obj in objs_to_remove:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                # best-effort removal
                pass
        # Optionally remove orphan data
        # Blender will keep data-blocks until users==0
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                try:
                    bpy.data.meshes.remove(mesh)
                except Exception:
                    pass


def ensure_collection(name: str) -> bpy.types.Collection:
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll

if __name__ == "__main__":
    # Parse Blender CLI args (everything after '--') using argparse
    raw_argv = sys.argv
    if '--' in raw_argv:
        raw_argv = raw_argv[raw_argv.index('--') + 1:]
    else:
        raw_argv = []

    parser = argparse.ArgumentParser(description="Discrete light contrastive setup")
    parser.add_argument('folder', nargs='?', default=None, help='Path to folder containing focus object files')
    args = parser.parse_args(raw_argv)

    # folder_arg = args.folder
    folder_arg = r'C:\Users\yaboy\Downloads\test_set_of_glb_files' # TODO: replace this with args.folder for actual usage

    active_cam = bpy.context.scene.camera

    object_loader = ObjectLoader()

    focus_object = None

    # If a folder is provided, pick a random compatible model and import it
    if folder_arg:
        if os.path.isdir(folder_arg):
            clear_collection_objects('Focus_Objects')
            supported = ('.glb', '.gltf', '.fbx')
            files = [f for f in os.listdir(folder_arg) if f.lower().endswith(supported)]
            print(f"Found {len(files)} compatible files in folder: {folder_arg}", flush=True)
            print("Files:", files, flush=True)
            if not files:
                print(f"No compatible files found. Supported: {supported}")
            else:
                chosen = random.choice(files)
                chosen_path = os.path.join(folder_arg, chosen)
                print(f"Importing focus object: {chosen_path}")
                imported_obj = object_loader.import_object(chosen_path)

                # Get all selected objects (the import selects them)
                imported_objects = list(bpy.context.selected_objects)

                coll = ensure_collection('Focus_Objects')
                # Move imported (selected) objects into the Focus_Objects collection
                for obj in imported_objects:
                    try:
                        if obj.name not in coll.objects:
                            coll.objects.link(obj)
                    except Exception:
                        pass

                # Merge all imported meshes into one and set origin
                focus_object = object_loader.preprocess_object(imported_objects)
        else:
            print(f"Provided folder path does not exist: {folder_arg}")

    if not focus_object:
        print("Error: No focus object found or imported. Exiting.")
    else:
        plane_to_scatter_on = bpy.data.objects.get("scatter_plane")
        random_point_on_plane = get_random_point_on_surface(plane_to_scatter_on)
        
        # Set the focus object's location to the random point on the plane
        focus_object.location = random_point_on_plane
        # Randomly rotate around the z axis
        focus_object.rotation_euler.z = random.uniform(0, 2 * math.pi)

        # camera_spawner = CameraSpawner("look_from_volume", focus_object.name, active_cam.name, use_look_at_volume_exact_location=True)
        # camera_spawner.update(random.randint(0, 10000), restore_hidden_state=True)
        
        # generator = DiscreteLightGenerator()
        # generator.set_seed(random.randint(0, 10000))
        # generator.generate_lights(focus_object, active_cam)