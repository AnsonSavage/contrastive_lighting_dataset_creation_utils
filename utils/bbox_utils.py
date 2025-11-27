import bpy
from mathutils import Vector
from typing import Tuple


def get_bbox_extrema(obj: bpy.types.Object) -> Tuple[Vector, Vector]:
    """
    Calculates the world space bounding box extrema for an object.
    
    Args:
        obj: The Blender object to get the bounding box for.
        
    Returns:
        A tuple of (min_bound, max_bound) Vectors representing the
        minimum and maximum corners of the world-space bounding box.
    """
    # Force update to ensure bounding box is correct
    bpy.context.view_layer.update()

    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    
    min_bound = Vector((
        min(v.x for v in bbox_corners),
        min(v.y for v in bbox_corners),
        min(v.z for v in bbox_corners),
    ))
    max_bound = Vector((
        max(v.x for v in bbox_corners),
        max(v.y for v in bbox_corners),
        max(v.z for v in bbox_corners),
    ))
    
    return min_bound, max_bound
