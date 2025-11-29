import bpy
import random
from mathutils import Vector

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
    from utils.bbox_utils import get_bbox_extrema
    from utils.visibility_utils import is_point_inside_mesh

    # Use a local RNG if a seed is provided to avoid mutating global random state
    rng = random if seed is None else random.Random(seed)
    if obj.type != 'MESH' or obj.data is None:
        print("Error: The provided object is not a valid mesh.")
        return None

    # 1. Check if the object's bounding box is already in the cache
    if obj in mesh_cache:
        min_bound, max_bound = mesh_cache[obj]
        print(f"Retrieved bounding box for '{obj.name}' from cache.")
    else:
        print(f"Calculating bounding box for '{obj.name}' and caching it.")
        min_bound, max_bound = get_bbox_extrema(obj)
        # Store the calculated bounds in the global cache
        mesh_cache[obj] = (min_bound, max_bound)

    # Add a small buffer to the bounding box to avoid surface issues
    buffer = 0.0001
    min_bound = min_bound - Vector((buffer, buffer, buffer))
    max_bound = max_bound + Vector((buffer, buffer, buffer))

    for i in range(max_attempts):
        random_point_world = Vector((
            rng.uniform(min_bound.x, max_bound.x),
            rng.uniform(min_bound.y, max_bound.y),
            rng.uniform(min_bound.z, max_bound.z)
        ))


        # Transform the ray into the object's local space
        if is_point_inside_mesh(obj, random_point_world):
            print(f"Found a point inside after {i + 1} attempts.")
            return random_point_world
    
    print(f"Failed to find an interior point after {max_attempts} attempts.")
    return None

def get_random_point_on_surface(obj, seed=None):
    """
    Finds a random point on the surface of a given Blender mesh object.

    Args:
        obj (bpy.types.Object): The mesh object to sample from.

        seed (int, optional): If provided, uses a local RNG seeded with this value for deterministic sampling.

    Returns:
        mathutils.Vector or None: A Vector representing the location of a random point on the surface, or None if unsuccessful.
    
        Thanks to https://blender.stackexchange.com/a/221597/12805
    """
    import bmesh
    
    rng = random if seed is None else random.Random(seed)
    
    if obj.type != 'MESH':
        return None
    
    # Create a BMesh from the object mesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    
    # Triangulate so we have consistent faces (triangles)
    
    bm.faces.ensure_lookup_table()
    
    # Calculate total area and choose a random value
    total_area = sum(f.calc_area() for f in bm.faces)
    if total_area <= 0:
        bm.free()
        return None
        
    target_area = rng.uniform(0, total_area)
    
    current_area = 0
    chosen_face = None
    
    # Select a face based on area weight
    for face in bm.faces:
        current_area += face.calc_area()
        if current_area >= target_area:
            chosen_face = face
            break
            
    if chosen_face is None:
        chosen_face = bm.faces[-1]
        
    # Sample a point on the chosen triangle
    # Using barycentric coordinates
    v1 = chosen_face.verts[0].co
    v2 = chosen_face.verts[1].co
    v3 = chosen_face.verts[2].co
    
    u = rng.random()
    v = rng.random()
    
    if u + v > 1:
        u = 1 - u
        v = 1 - v
        
    w = 1 - u - v
    
    point_local = u * v1 + v * v2 + w * v3
    point_world = obj.matrix_world @ point_local
    
    bm.free()
    
    return point_world
    
