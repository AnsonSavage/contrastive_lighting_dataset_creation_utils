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


def bboxes_intersect(min1: Vector, max1: Vector, min2: Vector, max2: Vector) -> bool:
    """Check if two axis-aligned bounding boxes intersect."""
    return (min1.x <= max2.x and max1.x >= min2.x and
            min1.y <= max2.y and max1.y >= min2.y and
            min1.z <= max2.z and max1.z >= min2.z)
