import bpy
import mathutils

import math
import random
from mathutils import Vector, Matrix
import importlib

def hacky_stuff_to_make_environment_work():
    import sys
    # Check if we are actually in a Text Editor and a script is open
    import os
    # Set environment variables
    # BLENDER_PATH="/groups/procedural_research/blender-4.5.3-linux-x64/blender"
    # DATA_PATH="/groups/procedural_research/data/procedural_dataset_generation_data"
    os.environ['BLENDER_PATH'] = "/groups/procedural_research/blender-4.5.3-linux-x64/blender"
    os.environ['DATA_PATH'] = "/groups/procedural_research/data/procedural_dataset_generation_data"
    active_text_block = bpy.context.edit_text
    if not active_text_block:
        raise Exception("No active script in the Text Editor. Please run from the Text Editor window.")

    # Get the filepath associated with this text block
    script_filepath = active_text_block.filepath

    # Check if the script has been saved to disk
    if not script_filepath:
        raise Exception("The script is not saved to an external .py file. Please save it first.")

    # Get the directory of the script file
    # For /path/to/script.py, this will be /path/to
    script_directory = os.path.dirname(script_filepath)

    # Reload modules
    if str(script_directory) in sys.path:
        # Remove it first to avoid duplicates
        sys.path.remove(str(script_directory))
    print("Adding current directory to sys.path:", str(script_directory))
    sys.path.append(str(script_directory))
    importlib.reload(sys.modules.get('data.image_text_instructions_task'))
    importlib.reload(sys.modules.get('render_manager'))

hacky_stuff_to_make_environment_work()
from data.image_text_instructions_task import ImageTextInstructSignatureVector
from render_manager import ImageTextRenderManager
from data.signature_vector.light_attribute import HDRIName, KeyLight, FillLight, RimLight, VirtualLight, LightSize, LightDirection, LightIntensity, BlackbodyLightColor

def sample_cone(normal: Vector, theta_max_deg: float) -> Vector:
    theta_max = math.radians(theta_max_deg)
    u = random.random()
    v = random.random()
    cos_theta = (1 - u) + u * math.cos(theta_max)
    sin_theta = math.sqrt(1 - cos_theta * cos_theta)
    phi = 2 * math.pi * v
    # Local direction (cone axis is +Z)
    dir_local = Vector((sin_theta * math.cos(phi), sin_theta * math.sin(phi), cos_theta))
    # Build orthonormal basis
    def basis_from_normal(n):
        n = n.normalized()
        if abs(n.z) < 0.999:
            t = n.cross(Vector((0,0,1))).normalized()
        else:
            t = n.cross(Vector((0,1,0))).normalized()
        b = n.cross(t)
        return Matrix((t, b, n)).transposed()
    M = basis_from_normal(normal)
    return (M @ dir_local).normalized()


def set_camera_focus_object(cam: bpy.types.Object, obj: bpy.types.Object) -> None:
    assert cam.type == 'CAMERA'
    cam.data.dof.use_dof = True
    cam.data.dof.focus_object = obj
    cam.data.dof.aperture_fstop = 0.5

def add_reverse_key_light(cam: bpy.types.Object, obj: bpy.types.Object, light_size:float = 1.5, remove_existing: bool = True) -> None:
    # TODO: You need to be able to randomly sample distances, sizes, strengths, colors, etc.
    if remove_existing:
        for light in [o for o in bpy.context.scene.objects if o.type == 'LIGHT' and 'Reverse_Key_Light' in o.name]:
            bpy.data.objects.remove(light, do_unlink=True)
        for plane in [o for o in bpy.context.scene.objects if o.type == 'MESH' and 'Bounce_Plane' in o.name]:
            bpy.data.objects.remove(plane, do_unlink=True)
    assert cam.type == 'CAMERA'
    
    camera_to_object = obj.location - cam.location

    # Normalize it
    camera_to_object_length = camera_to_object.length
    camera_to_object.normalize()


    # Reflect the vector across the Z axis
    z_axis = mathutils.Vector((0, 0, 1))
    object_to_light = camera_to_object.reflect(z_axis)

    distance_from_object = camera_to_object_length  # Arbitrary value, to be controlled later
    camera_left = z_axis.cross(camera_to_object).normalized()
    camera_right = -camera_left

    # stochastically decide whether the reverse keylight will be to the left or right of the camera
    camera_left_right_amount = 0.8
    if random.random() < 0.5:
        object_to_light += camera_right * camera_left_right_amount
    else:
        object_to_light += camera_left * camera_left_right_amount
    
    object_to_light += z_axis * 0.5  # Slightly above the object, you can sample this distance randomly as well
    object_to_light.normalize()

    object_to_light = sample_cone(object_to_light, 15)
    # Set the Z axis to be positive
    if object_to_light.z < 0:
        object_to_light.z *= -1
    object_to_light.normalize()
    light_location = obj.location + object_to_light * distance_from_object

    # Create a new light data block
    light_data = bpy.data.lights.new(name="Reverse_Key_Light", type='AREA')
    light_data.size = light_size
    light_data.energy = 800  # Adjust the energy as needed
    light_object = bpy.data.objects.new(name="Reverse_Key_Light", object_data=light_data)
    light_object.location = light_location
    bpy.context.collection.objects.link(light_object)

    # Point the light at the object using a track to constraint
    constraint = light_object.constraints.new(type='TRACK_TO')
    constraint.target = obj

    # Add a plane as a bounce light reflector
    plane_size = light_size * 2
    plane_location = obj.location - object_to_light * camera_to_object_length + z_axis * 0.5
    bpy.ops.mesh.primitive_plane_add(size=plane_size, location=plane_location)
    # add track to constraint to the plane to face the object
    plane_object = bpy.context.active_object
    plane_object.name = "Bounce_Plane"
    constraint = plane_object.constraints.new(type='TRACK_TO')
    constraint.target = obj



# cam = bpy.data.objects.get('Camera')
# obj = bpy.data.objects.get('Statue')

# set_camera_focus_object(cam, obj)
# add_reverse_key_light(cam, obj)

def get_distance_between_objects(obj1: bpy.types.Object, obj2: bpy.types.Object) -> float:
    return (obj1.location - obj2.location).length

obj = bpy.data.objects.get('light_focus')

def process_signature_vector(
    signature_vector: ImageTextInstructSignatureVector
) -> None:
    primary_light = signature_vector.variant_attributes[0]
    primary_light_intensity = primary_light.light_intensity
    ImageTextRenderManager()._sample_light_intensity(
        light_name='TriLamp-Key',
        distance_from_object=get_distance_between_objects(bpy.data.objects.get('TriLamp-Key'), obj),
        intensity=primary_light_intensity,
        sample_seed=random.randint(0, 1e6)
    )
    ImageTextRenderManager()._sample_light_color_blackbody(
        light_name='TriLamp-Key',
        blackbody_color=primary_light.light_color,
        sample_seed=random.randint(0, 1e6)
    )
        
    # fill_light = signature_vector.variant_attributes[1]
    # rim_light = signature_vector.variant_attributes[2]
    

text_signature_vector = ImageTextInstructSignatureVector(
    variant_attributes=(
        KeyLight(
            light_size=LightSize.MEDIUM,
            light_direction=LightDirection.FRONT_RIGHT,
            light_intensity=LightIntensity.HIGH,
            light_color=BlackbodyLightColor.WARM
        ),
        FillLight(
            light_size=LightSize.MEDIUM,
            light_direction=LightDirection.FRONT_LEFT,
            light_intensity=LightIntensity.MEDIUM,
            light_color=BlackbodyLightColor.COOL
        ),
        RimLight(
            light_size=LightSize.MEDIUM,
            light_direction=LightDirection.BACK_LEFT,
            light_intensity=LightIntensity.MEDIUM,
            light_color=BlackbodyLightColor.NEUTRAL
        )),
        invariant_attributes=(
            None, # TODO: We'll have to pull this in. Also, we're currently setting up the scene beforehand :shrug:
            None,
            None
        )
    )

process_signature_vector(text_signature_vector)