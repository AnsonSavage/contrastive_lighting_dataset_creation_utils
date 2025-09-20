import bpy

def add_empty_at_location(location, name="Visualizer", scale=0.1, update_location_if_exists=True):
    """
    Adds an Empty object at the specified location in the scene.

    Args:
        location (mathutils.Vector): The location to place the Empty.
        name (str): The name of the new Empty object.
        scale (float): The scale of the new Empty object.

    Returns:
        bpy.types.Object: The newly created Empty object.
    """
    existing_obj = bpy.data.objects.get(name)
    
    bpy.ops.object.empty_add(type='PLAIN_AXES', align='WORLD', location=location)
    empty_obj = bpy.context.active_object
    empty_obj.name = name
    empty_obj.scale = (scale, scale, scale)
    return empty_obj