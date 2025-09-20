import bpy
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
