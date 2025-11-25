import bpy
import random
import math
from mathutils import Vector, Matrix, Euler


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

    def sample_cone(self, normal: Vector, theta_max_deg: float) -> Vector:
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

    @staticmethod
    def hsv_to_rgb(h, s, v):
        import colorsys
        return colorsys.hsv_to_rgb(h, s, v)

    def generate_lights(self, target_object, camera):
        if not target_object or not camera:
            print("Error: Select an object and ensure a camera exists.")
            return

        self.clear_previous_lights()

        # Create Collection
        if self.collection_name not in bpy.data.collections:
            light_collection = bpy.data.collections.new(self.collection_name)
            bpy.context.scene.collection.children.link(light_collection)
        else:
            light_collection = bpy.data.collections[self.collection_name]

        num_lights = self.rng.randint(self.min_lights, self.max_lights)

        cam_rot_mat = camera.matrix_world.to_quaternion().to_matrix()

        target_loc = target_object.location
        
        # We define the "Up" direction for the hemisphere.
        # Using Global Z (0,0,1) ensures we don't intersect the floor.
        # If you wanted the lights to come from the camera's direction, you would use:
        # cone_axis = active_cam.matrix_world.to_quaternion() @ Vector((0,0,-1))
        cone_axis = Vector((0, 0, 1)) 

        print(f"Generating {num_lights} lights in a {self.max_cone_angle} degree cone...")

        light_objs = []
        for i in range(num_lights):
            # 1. Random Props (use per-instance RNG)
            dist = self.rng.uniform(self.min_dist, self.max_dist)
            size = self.rng.uniform(self.min_size, self.max_size)
            power = self.rng.uniform(self.min_power, self.max_power)
            color_rgb = self.hsv_to_rgb(self.rng.random(), self.rng.uniform(self.saturation_min, self.saturation_max), 1.0)

            # 2. Calculate Position using sample_cone
            # This returns a unit vector pointing somewhere in the sky
            direction_vec = self.sample_cone(cone_axis, self.max_cone_angle)
            
            # Scale by distance
            local_vec = direction_vec * dist

            matrix_to_align_camera_with_y_axis = self.get_matrix_to_align_with_camera_looking_down_y_axis(camera)
            aligned_vec = matrix_to_align_camera_with_y_axis @ local_vec
            
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

            light_objs.append(light_obj)

        bpy.context.view_layer.update()
        self.post_check_light_visibility(light_objs, target_object)
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

    def check_visibility(self, light_pos, target_obj):
        scene = bpy.context.scene
        depsgraph = bpy.context.evaluated_depsgraph_get()
        
        # 1. Check center
        target_center = target_obj.matrix_world.translation
        direction = target_center - light_pos
        dist = direction.length
        if dist < 1e-4: # If we're close, consider it visible
            return True
            
        success, location, normal, index, object, matrix = scene.ray_cast(depsgraph, light_pos, direction.normalized())
        
        if success and object == target_obj:
            return True
            
        # 2. Check a subset of vertices to see if any of them are visible from the light
        if target_obj.type == 'MESH':
            mw = target_obj.matrix_world
            mesh = target_obj.data
            vertices = mesh.vertices
            
            step = max(1, len(vertices) // 50) 
            
            for i in range(0, len(vertices), step):
                v = vertices[i]
                v_world = mw @ v.co
                direction = v_world - light_pos
                dist = direction.length
                
                if dist < 1e-6:
                    continue
                    
                success, location, normal, index, object, matrix = scene.ray_cast(depsgraph, light_pos, direction.normalized(), distance=dist + 1.0)
                
                if success and object == target_obj:
                    return True
                    
        return False

    def post_check_light_visibility(self, light_objs, target_obj):
        visible_count = 0
        for light_obj in light_objs:
            pos = light_obj.location
            if self.check_visibility(pos, target_obj):
                print(f"Light {light_obj.name} is visible to the target object.")
                visible_count += 1
            else:
                print(f"Light {light_obj.name} is NOT visible to the target object.")
        print(f"{visible_count}/{len(light_objs)} lights are visible to the target object.")
