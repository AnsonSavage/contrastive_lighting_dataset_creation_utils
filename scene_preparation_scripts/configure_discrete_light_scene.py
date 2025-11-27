import bpy
import bmesh

# --- Constants for Names ---
SCATTER_SURFACE_NAME = "scatter_surface"
CAMERA_NAME = "procedural_camera"
LOOK_FROM_VOLUME_NAME = "look_from_volume"
FOCUS_OBJECT_NAME = "focus_object"

FOCUS_OBJECTS_COLLECTION_NAME = "Focus_Objects"
BACKGROUND_OBJECTS_COLLECTION_NAME = "Background_Objects"

# Object Data Names
CAMERA_DATA_NAME = "procedural_camera_data"
LOOK_FROM_VOLUME_MESH_NAME = "look_from_volume_mesh"
SCATTER_SURFACE_MESH_NAME = "scatter_surface_mesh"

def get_or_create_collection(name):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    else:
        new_collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(new_collection)
        return new_collection

def setup_discrete_light_scene():
    """
    Sets up the scene with necessary objects and collections for the discrete light contrastive setup.
    """
    scene = bpy.context.scene

    # --- 1. Create Collections ---
    get_or_create_collection(FOCUS_OBJECTS_COLLECTION_NAME)
    get_or_create_collection(BACKGROUND_OBJECTS_COLLECTION_NAME)
    
    # --- 2. Create Objects ---

    # Camera
    if CAMERA_NAME not in bpy.data.objects:
        cam_data = bpy.data.cameras.new(name=CAMERA_DATA_NAME)
        cam_obj = bpy.data.objects.new(CAMERA_NAME, cam_data)
        scene.collection.objects.link(cam_obj)
        print(f"Added '{CAMERA_NAME}' to the scene.")
    else:
        print(f"'{CAMERA_NAME}' already exists.")
    
    # Look From Volume
    if LOOK_FROM_VOLUME_NAME not in bpy.data.objects:
        mesh_data = bpy.data.meshes.new(LOOK_FROM_VOLUME_MESH_NAME)
        obj = bpy.data.objects.new(LOOK_FROM_VOLUME_NAME, mesh_data)
        scene.collection.objects.link(obj)
        obj.display_type = 'WIRE'
        obj.hide_render = True
        
        # Create a default cube for look_from_volume
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=2.0)
        bm.to_mesh(mesh_data)
        bm.free()
        
        # Move it up a bit
        obj.location = (0, 0, 2)
        
        print(f"Added '{LOOK_FROM_VOLUME_NAME}' to the scene (default cube).")
    else:
        print(f"'{LOOK_FROM_VOLUME_NAME}' already exists.")

    # Scatter Surface
    if SCATTER_SURFACE_NAME not in bpy.data.objects:
        mesh_data = bpy.data.meshes.new(SCATTER_SURFACE_MESH_NAME)
        obj = bpy.data.objects.new(SCATTER_SURFACE_NAME, mesh_data)
        scene.collection.objects.link(obj)
        
        # Create a default plane for scatter surface
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=10) # 10x10 plane
        bm.to_mesh(mesh_data)
        bm.free()
        
        print(f"Added '{SCATTER_SURFACE_NAME}' to the scene (default 10x10 plane).")
    else:
        print(f"'{SCATTER_SURFACE_NAME}' already exists.")

    print("\nDiscrete light scene setup finished successfully.")

if __name__ == "__main__":
    setup_discrete_light_scene()
