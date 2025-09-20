import bpy

# --- Constants for Names ---
# Collection Names
CAMERAS_FOR_DATASET_COLL = 'cameras_for_dataset'
DEFAULT_COLL = 'default'
CUSTOM_COLL = 'custom'
PROCEDURAL_COLL = 'procedural'
AUX_COLL = 'aux'

# Object Names
PROCEDURAL_CAMERA_OBJ = 'procedural_camera'
LOOK_FROM_VOLUME_OBJ = 'look_from_volume'
LOOK_AT_VOLUME_OBJ = 'look_at_volume'

# Object Data Names
PROCEDURAL_CAMERA_DATA = 'procedural_camera_data'
LOOK_FROM_VOLUME_MESH = 'look_from_volume_mesh'
LOOK_AT_VOLUME_MESH = 'look_at_volume_mesh'


def get_or_create_collection(name, parent_collection):
    """
    Finds a collection by name within a parent collection. If it doesn't
    exist, it creates the collection, links it to the parent, and returns it.

    Args:
        name (str): The name of the collection to find or create.
        parent_collection (bpy.types.Collection): The parent collection.

    Returns:
        bpy.types.Collection: The found or newly created collection.
    """
    if name in parent_collection.children:
        return parent_collection.children[name]
    else:
        new_collection = bpy.data.collections.new(name)
        parent_collection.children.link(new_collection)
        return new_collection

def get_all_child_collections(parent_collection):
    """
    Recursively gets all descendant collections of a given collection.

    Args:
        parent_collection (bpy.types.Collection): The collection to start from.

    Returns:
        set: A set containing all descendant collections.
    """
    child_colls = set()
    for child in parent_collection.children:
        child_colls.add(child)
        child_colls.update(get_all_child_collections(child))
    return child_colls

def setup_camera_collections():
    """
    Main function to set up the collection hierarchy, organize existing
    cameras, and add new specified objects.
    """
    scene = bpy.context.scene

    # --- 1. Create Collection Hierarchy ---
    # Ensure the main 'cameras_for_dataset' collection exists at the scene level
    if CAMERAS_FOR_DATASET_COLL in scene.collection.children:
        cameras_for_dataset_coll = scene.collection.children[CAMERAS_FOR_DATASET_COLL]
    else:
        cameras_for_dataset_coll = bpy.data.collections.new(CAMERAS_FOR_DATASET_COLL)
        scene.collection.children.link(cameras_for_dataset_coll)

    # Create the sub-collections using the helper function
    default_coll = get_or_create_collection(DEFAULT_COLL, cameras_for_dataset_coll)
    custom_coll = get_or_create_collection(CUSTOM_COLL, cameras_for_dataset_coll)
    procedural_coll = get_or_create_collection(PROCEDURAL_COLL, cameras_for_dataset_coll)
    aux_coll = get_or_create_collection(AUX_COLL, procedural_coll)

    # --- 2. Organize Existing Cameras ---
    # Get a set of all collections that are part of our new hierarchy
    dataset_collections_set = get_all_child_collections(cameras_for_dataset_coll)
    dataset_collections_set.add(cameras_for_dataset_coll)

    # Identify cameras that are not part of the hierarchy
    cameras_to_move = []
    for obj in scene.objects:
        if obj.type == 'CAMERA':
            is_in_hierarchy = False
            # Check if any of the object's parent collections are in our hierarchy
            for coll in obj.users_collection:
                if coll in dataset_collections_set:
                    is_in_hierarchy = True
                    break
            
            if not is_in_hierarchy:
                cameras_to_move.append(obj)

    # Move the identified cameras into the 'default' collection
    if cameras_to_move:
        print(f"Found {len(cameras_to_move)} camera(s) to organize...")
        for cam in cameras_to_move:
            print(f"  - Moving '{cam.name}' to '{default_coll.name}' collection.")
            # Unlink from all current collections
            original_collections = [coll for coll in cam.users_collection]
            for coll in original_collections:
                coll.objects.unlink(cam)
            
            # Link to the 'default' collection
            default_coll.objects.link(cam)

    # --- 3. Add New Objects ---
    # Add 'procedural_camera' if it doesn't exist
    if PROCEDURAL_CAMERA_OBJ not in bpy.data.objects:
        cam_data = bpy.data.cameras.new(name=PROCEDURAL_CAMERA_DATA)
        cam_obj = bpy.data.objects.new(PROCEDURAL_CAMERA_OBJ, cam_data)
        procedural_coll.objects.link(cam_obj)
        print(f"Added '{PROCEDURAL_CAMERA_OBJ}' to the '{procedural_coll.name}' collection.")
    
    # Add 'look_from_volume' empty mesh if it doesn't exist
    if LOOK_FROM_VOLUME_OBJ not in bpy.data.objects:
        mesh_from_data = bpy.data.meshes.new(LOOK_FROM_VOLUME_MESH)
        obj_from = bpy.data.objects.new(LOOK_FROM_VOLUME_OBJ, mesh_from_data)
        aux_coll.objects.link(obj_from)
        
        # Set viewport display to wireframe and disable render visibility
        obj_from.display_type = 'WIRE'
        obj_from.hide_render = True
        
        print(f"Added '{LOOK_FROM_VOLUME_OBJ}' to the '{aux_coll.name}' collection.")

    # Add 'look_at_volume' empty mesh if it doesn't exist
    if LOOK_AT_VOLUME_OBJ not in bpy.data.objects:
        mesh_at_data = bpy.data.meshes.new(LOOK_AT_VOLUME_MESH)
        obj_at = bpy.data.objects.new(LOOK_AT_VOLUME_OBJ, mesh_at_data)
        aux_coll.objects.link(obj_at)

        # Set viewport display to wireframe and disable render visibility
        obj_at.display_type = 'WIRE'
        obj_at.hide_render = True
        
        print(f"Added '{LOOK_AT_VOLUME_OBJ}' to the '{aux_coll.name}' collection.")
        
    print("\nScript finished successfully.")


# --- This allows the script to be run from the Blender text editor ---
if __name__ == "__main__":
    setup_camera_collections()
