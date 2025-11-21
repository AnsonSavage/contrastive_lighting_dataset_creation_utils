import bpy
import random
import math
from mathutils import Vector, Matrix
import sys

sys.path.append(r'C:\Users\yaboy\OneDrive\Documents\BYU\Masters_Thesis\contrastive_lighting_dataset_creation_utils')
from camera_spawner import CameraSpawner

class DiscreteLightGenerator:
    def __init__(self, seed=21, collection_name="Generated_Lighting"):
        self.seed = seed
        self.collection_name = collection_name
        
        # Cone Angle
        # 90.0 = Full Hemisphere (down to the floor)
        # 80.0 = Stops 10 degrees before hitting the floor (safer)
        self.max_cone_angle = 80.0

        # Light Count
        self.min_lights = 1
        self.max_lights = 4

        # Distance / Size / Power
        self.min_dist = 2.0
        self.max_dist = 10.0
        self.min_size = 0.5
        self.max_size = 2.0
        self.min_power = 200.0
        self.max_power = 1000.0

        # Saturation
        self.saturation_min = 0.1
        self.saturation_max = 0.9

    def sample_cone(self, normal: Vector, theta_max_deg: float) -> Vector:
        """
        Generates a random unit vector within a cone defined by a normal and max angle.
        Uniformly distributed over the solid angle.
        """
        theta_max = math.radians(theta_max_deg)
        u = random.random()
        v = random.random()
        
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

    @staticmethod
    def hsv_to_rgb(h, s, v):
        import colorsys
        return colorsys.hsv_to_rgb(h, s, v)

    def generate_lights(self, target_object, camera):
        if not target_object or not camera:
            print("Error: Select an object and ensure a camera exists.")
            return

        self.clear_previous_lights()
        random.seed(self.seed)

        # Create Collection
        if self.collection_name not in bpy.data.collections:
            light_collection = bpy.data.collections.new(self.collection_name)
            bpy.context.scene.collection.children.link(light_collection)
        else:
            light_collection = bpy.data.collections[self.collection_name]

        num_lights = random.randint(self.min_lights, self.max_lights)

        cam_rot_mat = camera.matrix_world.to_quaternion().to_matrix()

        target_loc = target_object.location
        
        # We define the "Up" direction for the hemisphere.
        # Using Global Z (0,0,1) ensures we don't intersect the floor.
        # If you wanted the lights to come from the camera's direction, you would use:
        # cone_axis = active_cam.matrix_world.to_quaternion() @ Vector((0,0,-1))
        cone_axis = Vector((0, 0, 1)) 

        print(f"Generating {num_lights} lights in a {self.max_cone_angle} degree cone...")

        for i in range(num_lights):
            # 1. Random Props
            dist = random.uniform(self.min_dist, self.max_dist)
            size = random.uniform(self.min_size, self.max_size)
            power = random.uniform(self.min_power, self.max_power)
            color_rgb = self.hsv_to_rgb(random.random(), random.uniform(self.saturation_min, self.saturation_max), 1.0)

            # 2. Calculate Position using sample_cone
            # This returns a unit vector pointing somewhere in the sky
            direction_vec = self.sample_cone(cone_axis, self.max_cone_angle)
            
            # Scale by distance
            local_vec = direction_vec * dist

            aligned_vec = cam_rot_mat @ local_vec
            
            final_pos = target_loc + aligned_vec

            # 3. Create Light
            light_data = bpy.data.lights.new(name=f"GenLight_{self.seed}_{i}", type='AREA')
            light_obj = bpy.data.objects.new(name=f"GenLight_{self.seed}_{i}", object_data=light_data)
            
            light_collection.objects.link(light_obj)
            
            light_obj.location = final_pos
            light_data.energy = power
            light_data.color = color_rgb
            light_data.shape = 'SQUARE'
            light_data.size = size

            # 4. Point Light at Object
            direction = target_loc - light_obj.location
            light_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

        bpy.context.view_layer.update()
        print("Done.")
    
    def set_seed(self, new_seed):
        self.seed = new_seed

if __name__ == "__main__":
    focus_object = bpy.data.objects.get("focus_object")
    active_cam = bpy.context.scene.camera
    camera_spawner = CameraSpawner("look_from_volume", focus_object.name, active_cam.name, use_look_at_volume_exact_location=True)
    camera_spawner.update(random.randint(0, 10000), restore_hidden_state=True)
    
    generator = DiscreteLightGenerator()
    generator.set_seed(random.randint(0, 10000))
    generator.generate_lights(focus_object, active_cam)