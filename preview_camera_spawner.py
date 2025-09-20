import bpy
import mathutils
import random
from mathutils import Vector
from math import inf

# A global dictionary to cache mesh data (e.g., bounding boxes)
# This maps a bpy.types.Object to its calculated data and assumes the object won't change.
mesh_cache = {}

def get_random_point_in_mesh(obj, max_attempts=3000, seed=None):
    """
    Finds a random point inside the volume of a given Blender mesh object.
    Caches bounding box data to speed up repeated calls on the same object.

    Args:
        obj (bpy.types.Object): The mesh object to sample from. It must be a closed, manifold mesh.

        max_attempts (int): Maximum number of attempts to find a point.
        seed (int, optional): If provided, uses a local RNG seeded with this value for deterministic sampling.

    Returns:
        mathutils.Vector or None: A Vector representing the location of a random point 
                                  inside the mesh, or None if a point could not be found.
    """
    # Use a local RNG if a seed is provided to avoid mutating global random state
    rng = random if seed is None else random.Random(seed)
    if obj.type != 'MESH' or obj.data is None:
        print("Error: The provided object is not a valid mesh.")
        return None

    min_bound, max_bound = None, None

    # 1. Check if the object's bounding box is already in the cache
    if obj in mesh_cache:
        min_bound, max_bound = mesh_cache[obj]
        print(f"Retrieved bounding box for '{obj.name}' from cache.")
    else:
        print(f"Calculating bounding box for '{obj.name}' and caching it.")
        # Get the dependency graph
        depsgraph = bpy.context.evaluated_depsgraph_get()
        
        # Using to_mesh() and to_mesh_clear() in a try/finally block is the most
        # robust way to handle temporary mesh data and prevent memory leaks.
        mesh = None
        try:
            mesh = obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            
            matrix_world = obj.matrix_world
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
            
            # Store the calculated bounds in the global cache
            mesh_cache[obj] = (temp_min_bound, temp_max_bound)
            min_bound, max_bound = temp_min_bound, temp_max_bound
        
        finally:
            if mesh:
                obj.to_mesh_clear()

    if min_bound is None or max_bound is None:
        print("Error: Could not determine mesh bounds.")
        return None

    # Add a small buffer to the bounding box to avoid surface issues
    buffer = 0.0001
    min_bound = min_bound - Vector((buffer, buffer, buffer))
    max_bound = max_bound + Vector((buffer, buffer, buffer))

    # 2. Find a point inside the mesh using ray casting
    for i in range(max_attempts):
        random_point = Vector((
            rng.uniform(min_bound.x, max_bound.x),
            rng.uniform(min_bound.y, max_bound.y),
            rng.uniform(min_bound.z, max_bound.z)
        ))

        ray_direction = Vector((1, 0, 0))
        intersections = 0
        current_point = random_point
        
        while True:
            hit, location, normal, index = obj.ray_cast(current_point, ray_direction)
            if not hit:
                break
            intersections += 1
            current_point = location + ray_direction * 0.0001

        if intersections % 2 == 1:
            print(f"Found a point inside after {i + 1} attempts.")
            return random_point

    print(f"Failed to find an interior point after {max_attempts} attempts.")
    return None


class CameraSpawner:
    def __init__(self, look_from_volume_name, look_at_volume_name, camera_name):
        self.look_at_volume = bpy.data.objects.get(look_at_volume_name)
        assert self.look_at_volume is not None, f"Look at volume '{look_at_volume_name}' not found in the scene."
        self.look_from_volume = bpy.data.objects.get(look_from_volume_name)
        assert self.look_from_volume is not None, f"Look from volume '{look_from_volume_name}' not found in the scene."
        self.camera_name = camera_name

    def update(self, update_seed, pass_criteria = None):
        assert update_seed is not None, "Seed must be provided."
        # Initialize a deterministic RNG for this update call
        rng = random.Random(update_seed)
        has_good_sample = False
        max_attempts = 3000
        attempts = 0
        while not has_good_sample and attempts < max_attempts:
            # Generate seeds deterministically from the per-update RNG
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

    def compute_look_at_matrix(self, camera_position: mathutils.Vector, target_position: mathutils.Vector):
        """
        Computes a look-at transformation matrix for a camera.
        Args:
            camera_position (mathutils.Vector): The position of the camera.
            target_position (mathutils.Vector): The position the camera is looking at.
        Returns:
            mathutils.Matrix: The look-at transformation matrix.
        """
        camera_direction = (target_position - camera_position).normalized()

        up = mathutils.Vector((0, 0, 1))
        camera_right = camera_direction.cross(up).normalized()
        
        camera_up = camera_right.cross(camera_direction).normalized()

        rotation_transform = mathutils.Matrix([camera_right, camera_up, -camera_direction]).transposed().to_4x4()

        translation_transform = mathutils.Matrix.Translation(camera_position)
        print(translation_transform)
        look_at_transform = translation_transform @ rotation_transform
        return look_at_transform

def pass_criteria(look_from, look_at):
    return look_at.z < look_from.z

camera_spawner = CameraSpawner(
    look_from_volume_name='look_from_volume',
    look_at_volume_name='look_at_volume',
    camera_name='procedural_camera'
)

camera_spawner.update(update_seed=random.getrandbits(64), pass_criteria=pass_criteria)
