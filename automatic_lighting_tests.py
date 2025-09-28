import bpy
import mathutils

import math
import random
from mathutils import Vector, Matrix

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
    camera_left_right_amount = 1
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
    constraint = plane_object.constraints.new(type='TRACK_TO')
    constraint.target = obj






cam = bpy.data.objects.get('Camera')
obj = bpy.data.objects.get('Statue')

set_camera_focus_object(cam, obj)
add_reverse_key_light(cam, obj)