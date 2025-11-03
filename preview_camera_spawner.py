import bpy
import mathutils
import random
from mathutils import Vector
from math import inf

# A global dictionary to cache mesh data (e.g., bounding boxes)
mesh_cache = {}

def get_random_point_in_mesh(obj, max_attempts=300, seed=None):
    """
    Finds a random point inside the volume of a given Blender mesh object
    using scene.ray_cast in world space.

    Args:
        obj (bpy.types.Object): The mesh object to sample from. It must be a closed, manifold mesh.
        max_attempts (int): Maximum number of attempts to find a point.
        seed (int, optional): If provided, uses a local RNG seeded with this value.

    Returns:
        mathutils.Vector or None: A Vector (in world space) representing a random point 
                                  inside the mesh, or None if a point could not be found.
    """
    # Use a local RNG if a seed is provided
    rng = random if seed is None else random.Random(seed)
    if obj.type != 'MESH' or obj.data is None:
        print(f"Error: The provided object '{obj.name}' is not a valid mesh.")
        return None

    # Get the evaluated dependency graph and the current scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    scene = bpy.context.scene

    min_bound, max_bound = None, None

    # 1. Check if the object's bounding box is already in the cache
    if obj in mesh_cache:
        min_bound, max_bound = mesh_cache[obj]
        # print(f"Retrieved bounding box for '{obj.name}' from cache.")
    else:
        # print(f"Calculating bounding box for '{obj.name}' and caching it.")
        
        mesh = None
        try:
            # Get the evaluated mesh from the depsgraph
            mesh = obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            
            # This is the check that likely fails when the object is hidden
            if not mesh.vertices:
                print(f"Error: Mesh for '{obj.name}' has no vertices. Is it hidden?")
                return None
                
            matrix_world = obj.matrix_world
            
            # Calculate world-space bounding box
            temp_min_bound = Vector((inf, inf, inf))
            temp_max_bound = Vector((-inf, -inf, -inf))

            for vertex in mesh.vertices:
                world_co = matrix_world @ vertex.co
                temp_min_bound.x = min(temp_min_bound.x, world_co.x)
                temp_min_bound.y = min(temp_min_bound.y, world_co.y)
                temp_min_bound.z = min(temp_min_bound.z, world_co.z)
                temp_max_bound.x = max(temp_max_bound.x, world_co.x)
                temp_max_bound.y = max(temp_max_bound.y, world_co.y)
                temp_max_bound.z = max(temp_max_bound.z, world_co.z)
            
            mesh_cache[obj] = (temp_min_bound, temp_max_bound)
            min_bound, max_bound = temp_min_bound, temp_max_bound
        
        finally:
            if mesh:
                obj.to_mesh_clear()

    if min_bound is None or max_bound is None:
        print(f"Error: Could not determine mesh bounds for '{obj.name}'.")
        return None

    # Add a small buffer to the bounding box
    buffer = 0.0001
    min_bound = min_bound - Vector((buffer, buffer, buffer))
    max_bound = max_bound + Vector((buffer, buffer, buffer))

    # 2. Find a point inside the mesh using scene.ray_cast (world space)
    for i in range(max_attempts):
        # Generate a random point in world space
        random_point = Vector((
            rng.uniform(min_bound.x, max_bound.x),
            rng.uniform(min_bound.y, max_bound.y),
            rng.uniform(min_bound.z, max_bound.z)
        ))

        ray_direction = Vector((1, 0, 0)) # World space direction
        intersections = 0
        current_point = random_point # World space origin
        
        while True:
            hit, location, normal, index, hit_obj, matrix = scene.ray_cast(
                depsgraph, 
                current_point, 
                ray_direction
            )
            
            if not hit:
                break
                
            if hit_obj == obj:
                intersections += 1
                
            current_point = location + ray_direction * 0.0001

        if intersections % 2 == 1:
            print(f"Found a point inside '{obj.name}' after {i + 1} attempts.")
            return random_point

    print(f"Failed to find an interior point for '{obj.name}' after {max_attempts} attempts.")
    return None


class CameraSpawner:
    def __init__(self, look_from_volume_name, look_at_volume_name, camera_name):
        self.look_at_volume = bpy.data.objects.get(look_at_volume_name)
        assert self.look_at_volume is not None, f"Look at volume '{look_at_volume_name}' not found in the scene."
        self.look_from_volume = bpy.data.objects.get(look_from_volume_name)
        assert self.look_from_volume is not None, f"Look from volume '{look_from_volume_name}' not found in the scene."
        self.camera_name = camera_name

    def update(self, update_seed, pass_criteria = None):
        mesh_cache.clear()
        
        # --- NEW: Store original visibility state ---
        look_at_was_hidden = self.look_at_volume.hide_get()
        look_from_was_hidden = self.look_from_volume.hide_get()
        
        try:
            # --- NEW: Temporarily unhide objects ---
            if look_at_was_hidden:
                self.look_at_volume.hide_set(False)
                # print(f"Temporarily unhiding '{self.look_at_volume.name}'")
            
            if look_from_was_hidden:
                self.look_from_volume.hide_set(False)
                # print(f"Temporarily unhiding '{self.look_from_volume.name}'")

            # --- Original Logic ---
            assert update_seed is not None, "Seed must be provided."
            rng = random.Random(update_seed)
            has_good_sample = False
            max_attempts = 300
            attempts = 0
            
            look_at = None
            look_from = None
            
            while not has_good_sample and attempts < max_attempts:
                attempts += 1
                look_at_seed = rng.getrandbits(64)
                look_at = get_random_point_in_mesh(self.look_at_volume, seed=look_at_seed)
                if look_at is None:
                    continue
                    
                look_from_seed = rng.getrandbits(64)
                look_from = get_random_point_in_mesh(self.look_from_volume, seed=look_from_seed)
                if look_from is None:
                    continue
                    
                if pass_criteria is not None:
                    has_good_sample = pass_criteria(look_from, look_at)
                else:
                    has_good_sample = True

            if not has_good_sample:
                print(f"Failed to find valid camera positions after {max_attempts} attempts.")
                return

            camera = bpy.data.objects.get(self.camera_name)
            assert camera is not None, f"Camera '{self.camera_name}' not found in the scene."
            
            look_at_matrix = self.compute_look_at_matrix(look_from, look_at)
            
            camera.matrix_world = look_at_matrix
            
            print(f"Camera '{self.camera_name}' moved to coordinate: {look_from}")
            print(f"Camera '{self.camera_name}' now looking at: {look_at}")

        finally:
            # --- NEW: Restore original hidden state ---
            # This block runs *even if* the code in 'try' fails,
            # ensuring your scene is left as you found it.
            if look_at_was_hidden:
                self.look_at_volume.hide_set(True)
                # print(f"Restoring hidden state for '{self.look_at_volume.name}'")
            if look_from_was_hidden:
                self.look_from_volume.hide_set(True)
                # print(f"Restoring hidden state for '{self.look_from_volume.name}'")


    def compute_look_at_matrix(self, camera_position: mathutils.Vector, target_position: mathutils.Vector):
        """
        Computes a look-at transformation matrix for a camera.
        Args:
            camera_position (mathutils.Vector): The position of the camera.
            target_position (mathutils.Vector): The position the camera is looking at.
        Returns:
            mathutils.Matrix: The look-at transformation matrix.
        """
        if (camera_position - target_position).length_squared < 0.0001:
            print("Warning: Camera and target are at the same position.")
            return mathutils.Matrix.Translation(camera_position)

        camera_direction = (target_position - camera_position).normalized()

        up = mathutils.Vector((0, 0, 1))
        if abs(camera_direction.dot(up)) > 0.999:
            camera_right = mathutils.Vector((1, 0, 0)) 
            camera_up = camera_right.cross(camera_direction).normalized()
            camera_right = camera_direction.cross(camera_up).normalized()
        else:
            camera_right = camera_direction.cross(up).normalized()
            camera_up = camera_right.cross(camera_direction).normalized()

        rotation_transform = mathutils.Matrix([
            (*camera_right, 0),
            (*camera_up, 0),
            (*-camera_direction, 0),
            (0, 0, 0, 1)
        ]).transposed() 

        translation_transform = mathutils.Matrix.Translation(camera_position)
        
        look_at_transform = translation_transform @ rotation_transform
        return look_at_transform

def pass_criteria(look_from, look_at):
    direction = (look_at - look_from).normalized()
    looking_down = direction.z < -0.01 
    looking_straight_down = mathutils.Vector((0, 0, -1)).dot(direction) > 0.9
    return looking_down and not looking_straight_down

# --- This part runs the script ---
try:
    camera_spawner = CameraSpawner(
        look_from_volume_name='look_from_volume',
        look_at_volume_name='look_at_volume',
        camera_name='procedural_camera'
    )

    camera_spawner.update(update_seed=random.getrandbits(64), pass_criteria=pass_criteria)

except AssertionError as e:
    print(f"Script setup error: {e}")
