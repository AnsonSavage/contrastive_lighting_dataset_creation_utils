import bpy
from mathutils import Vector

def is_point_inside_mesh(obj, point_world) -> bool:
    """
    Determines if a given point in world space is inside the volume of the specified mesh object.

    Args:
        obj (bpy.types.Object): The mesh object to test against.
        point_world (mathutils.Vector): The point in world space to test.

    Returns:
        bool: True if the point is inside the mesh, False otherwise.
    """
    assert obj.type == 'MESH' and obj.data is not None, "Object must be a mesh with valid data."

    # Define ray direction in world space
    ray_direction = Vector((1, 0, 0)) # We can choose any arbitrary direction

    current_point_local = obj.matrix_world.inverted() @ point_world

    intersections = 0
    while True:
        # Cast in local space using the object's own ray_cast
        hit, location_local, normal_local, index = obj.ray_cast(current_point_local, ray_direction)

        if not hit:
            # No more hits along this ray in local space
            break

        intersections += 1
        # Advance slightly in local space to continue the ray
        current_point_local = location_local + ray_direction * 0.0001

    if intersections % 2 == 1:
        # Return the original world-space point
        return True
    return False

def check_visibility(origin, target_obj, pre_update_view_layer=True):
    if pre_update_view_layer:
        bpy.context.view_layer.update()
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    # 1. Check center
    target_center = target_obj.matrix_world.translation
    direction = target_center - origin
    dist = direction.length
    if dist < 1e-4: # If we're close, consider it visible
        return True
        
    success, location, normal, index, object, matrix = scene.ray_cast(depsgraph, origin, direction.normalized())
    
    if success and object == target_obj:
        return True
        
    # 2. Check a subset of vertices to see if any of them are visible from the origin
    if target_obj.type == 'MESH':
        mw = target_obj.matrix_world
        mesh = target_obj.data
        vertices = mesh.vertices
        
        step = max(1, len(vertices) // 50) 
        
        for i in range(0, len(vertices), step):
            v = vertices[i]
            v_world = mw @ v.co
            direction = v_world - origin
            dist = direction.length
            
            success, location, normal, index, object, matrix = scene.ray_cast(depsgraph, origin, direction.normalized(), distance=dist + 1.0)
            
            if success and object == target_obj:
                return True
            else:
                if success:
                    print(f"Ray hit object {object.name} before reaching target vertex.", flush=True)
                
    return False
