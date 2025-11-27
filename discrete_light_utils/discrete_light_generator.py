import bpy
import random
import math
from mathutils import Vector, Matrix, Euler
import colorsys
from utils.visibility_utils import check_visibility


class DiscreteLightGenerator:
    def __init__(self, collection_name="Generated_Lighting", seed=21):
        self.seed = seed
        self.collection_name = collection_name
        
        # Cone Angle (where 90.0 = Full Hemisphere)
        self.max_cone_angle = 70.0

        # Light Count
        self.min_lights = 1
        self.max_lights = 3

        # Distance / Size / Power
        self.min_dist = 2.5
        self.max_dist = 6.0
        self.min_size = 0.5
        self.max_size = 2.0
        self.min_power = 200.0
        self.max_power = 1000.0

        # Saturation
        self.saturation_min = 0.1
        self.saturation_max = 0.9

        # Per-instance RNG (so we don't mutate global random state)
        self.rng = random.Random(self.seed)
        
        # Current lights
        self.light_objects = []

    def _sample_cone(self, normal: Vector, theta_max_deg: float) -> Vector:
        """
        Generates a random unit vector within a cone defined by a normal and max angle.
        Uniformly distributed over the solid angle.
        """
        theta_max = math.radians(theta_max_deg)
        u = self.rng.random()
        v = self.rng.random()
        
        # Uniform distribution over the spherical cap
        cos_theta = (1 - u) + u * math.cos(theta_max)
        sin_theta = math.sqrt(1 - cos_theta * cos_theta)
        phi = 2 * math.pi * v
        
        # Local direction (cone axis is +Z)
        dir_local = Vector((sin_theta * math.cos(phi), sin_theta * math.sin(phi), cos_theta))
        
        # Build orthonormal basis from normal
        def basis_from_normal(n):
            n = n.normalized()
            # Handle the edge case where normal is close to Z-up
            if abs(n.z) < 0.999:
                t = n.cross(Vector((0,0,1))).normalized()
            else:
                t = n.cross(Vector((0,1,0))).normalized()
            b = n.cross(t)
            return Matrix((t, b, n)).transposed() # Transposed to align columns
        
        M = basis_from_normal(normal)
        return (M @ dir_local).normalized()

    def clear_previous_lights(self):
        if self.collection_name in bpy.data.collections:
            coll = bpy.data.collections[self.collection_name]
            objs_to_remove = [obj for obj in coll.objects]
            light_data_to_remove = {obj.data for obj in objs_to_remove if obj.data and obj.type == 'LIGHT'}
            
            for obj in objs_to_remove:
                bpy.data.objects.remove(obj, do_unlink=True)

            for light_data in light_data_to_remove:
                if light_data and light_data.users == 0:
                    bpy.data.lights.remove(light_data)
        self.light_objects = []

    @staticmethod
    def hsv_to_rgb(h, s, v):
        return colorsys.hsv_to_rgb(h, s, v)

    def align_lighting_configuration_to_target_object(self, target_object: bpy.types.Object):
        assert len(self.light_objects) > 0, "No lights to align."
        target_loc = target_object.location
        for light_obj in self.light_objects:
            light_obj.location += target_loc # Shift light position to be relative to target object

    def align_lighting_configuration_to_camera(self, camera: bpy.types.Object):
        assert len(self.light_objects) > 0, "No lights to align."

        matrix_to_align_camera_with_y_axis = self.get_matrix_to_align_with_camera_looking_down_y_axis(camera)
        rotation_matrix_4x4 = matrix_to_align_camera_with_y_axis.to_4x4()
        for light_obj in self.light_objects:
            # Rotate the light object around the world origin using the matrix
            light_obj.matrix_world = rotation_matrix_4x4 @ light_obj.matrix_world
    
    def _get_light_collection(self) -> bpy.types.Collection:
        # Create Collection
        if self.collection_name not in bpy.data.collections:
            light_collection = bpy.data.collections.new(self.collection_name)
            bpy.context.scene.collection.children.link(light_collection)
        else:
            light_collection = bpy.data.collections[self.collection_name]
        return light_collection

    def generate_light_configuration_from_seed(self):
        self.clear_previous_lights()
        light_collection = self._get_light_collection()
        num_lights = self.rng.randint(self.min_lights, self.max_lights)

        
        # We define the "Up" direction for the hemisphere.
        # Using Global Z (0,0,1) helps to avoid intersecting the floor.
        cone_axis = Vector((0, 0, 1)) 

        print(f"Generating {num_lights} lights in a {self.max_cone_angle} degree cone...", flush=True)
        
        for i in range(num_lights):
            # 1. Random Props (use per-instance RNG)
            dist = self.rng.uniform(self.min_dist, self.max_dist)
            size = self.rng.uniform(self.min_size, self.max_size)
            power = self.rng.uniform(self.min_power, self.max_power)
            color_rgb = self.hsv_to_rgb(self.rng.random(), self.rng.uniform(self.saturation_min, self.saturation_max), 1.0)

            # 2. Calculate Position using sample_cone
            # This returns a unit vector pointing somewhere in the sky
            direction_vec = self._sample_cone(cone_axis, self.max_cone_angle)
            
            # Compute its final position in local space
            local_pos = direction_vec * dist

            # 3. Create Light
            light_data = bpy.data.lights.new(name=f"GenLight_{self.seed}_{i}", type='AREA')
            light_obj = bpy.data.objects.new(name=f"GenLight_{self.seed}_{i}", object_data=light_data)
            
            light_collection.objects.link(light_obj)
            
            light_obj.location = local_pos
            light_data.energy = power
            light_data.color = color_rgb
            light_data.shape = 'SQUARE'
            light_data.size = size

            # 4. Point Light at origin
            direction = Vector((0, 0, 0)) - light_obj.location
            light_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

            self.light_objects.append(light_obj)

        print("Done.")
    
    def get_matrix_to_align_with_camera_looking_down_y_axis(self, camera: bpy.types.Object) -> Matrix:
        # camera_rotation_inverted = camera.matrix_world.to_quaternion().to_matrix().inverted() # should also be able to use the transpose b/c it's an orthonormal matrix
        # matrix_to_align_camera_with_y_axis = Euler((math.pi/2, 0, 0), 'XYZ').to_matrix() @ camera_rotation_inverted
        # return matrix_to_align_camera_with_y_axis.inverted()
        # Simplifies to:
        camera_rotation = camera.matrix_world.to_quaternion().to_matrix()
        return camera_rotation @ (Euler((math.pi/2, 0, 0), 'XYZ').to_matrix().transposed())

    def set_seed(self, new_seed):
        self.seed = new_seed
        self.rng = random.Random(self.seed)

    def verify_lighting_visible_to_target(self, target_obj) -> bool:
        bpy.context.view_layer.update()
        visible_count = 0
        for light_obj in self.light_objects:
            pos = light_obj.location
            if check_visibility(pos, target_obj, pre_update_view_layer=False):
                print(f"Light {light_obj.name} is visible to the target object.")
                visible_count += 1
            else:
                print(f"Light {light_obj.name} is NOT visible to the target object.")
        print(f"{visible_count}/{len(self.light_objects)} lights are visible to the target object.")
        return visible_count == len(self.light_objects)