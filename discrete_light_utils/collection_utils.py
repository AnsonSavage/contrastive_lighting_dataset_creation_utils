import bpy


def clear_collection_objects(collection_name: str):
    """Remove all objects in the named collection (and their data if unused)."""
    if collection_name in bpy.data.collections:
        coll = bpy.data.collections[collection_name]
        objs_to_remove = [obj for obj in coll.objects]
        for obj in objs_to_remove:
            try:
                bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                # best-effort removal
                pass
        # Optionally remove orphan data
        # Blender will keep data-blocks until users==0
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                try:
                    bpy.data.meshes.remove(mesh)
                except Exception:
                    pass


def ensure_collection(name: str) -> bpy.types.Collection:
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll
