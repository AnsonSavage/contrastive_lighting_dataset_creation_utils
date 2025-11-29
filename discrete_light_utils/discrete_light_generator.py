import bpy
import random
import math
from mathutils import Vector, Matrix, Euler
import colorsys
from utils.visibility_utils import check_visibility


class DiscreteLightGenerator:
    def __init__(self, collection_name="Generated_Lighting", seed=21, excluded_collection_name=None):
        self.rng = None
        self.set_seed(seed)
        self.collection_name = collection_name
        self.excluded_collection_name = excluded_collection_name
        
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
            
            # Cleanup Light Linking Collections
            for obj in objs_to_remove:
                # Find collections starting with "Light Linking for " + obj.name
                cols_to_remove = [c for c in bpy.data.collections if c.name.startswith(f"Light Linking for {obj.name}")]
                for c in cols_to_remove:
                    bpy.data.collections.remove(c)

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
            current_matrix = Matrix.Translation(light_obj.location) @ light_obj.rotation_euler.to_matrix().to_4x4() # This is a more efficient alternative to view_layer.update() followed by light_obj.matrix_world
            
            # Rotate the light object around the world origin using the matrix
            light_obj.matrix_world = rotation_matrix_4x4 @ current_matrix
    
    def _get_light_collection(self) -> bpy.types.Collection:
        # Create Collection
        if self.collection_name not in bpy.data.collections:
            light_collection = bpy.data.collections.new(self.collection_name)
            bpy.context.scene.collection.children.link(light_collection)
        else:
            light_collection = bpy.data.collections[self.collection_name]
        return light_collection

    def randomize_background(self):
        world = bpy.context.scene.world
        if not world:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world
        
        world.use_nodes = True
        
        # Get or create World Output node
        output_node = world.node_tree.nodes.get('World Output')
        if not output_node:
            for node in world.node_tree.nodes:
                if node.type == 'OUTPUT_WORLD':
                    output_node = node
                    break
        if not output_node:
            output_node = world.node_tree.nodes.new(type='ShaderNodeOutputWorld')

        # Get or create Background node
        bg_node = world.node_tree.nodes.get('Background')
        if not bg_node:
            # Try to find it by type if name is different
            for node in world.node_tree.nodes:
                if node.type == 'BACKGROUND':
                    bg_node = node
                    break
        
        if not bg_node:
            bg_node = world.node_tree.nodes.new(type='ShaderNodeBackground')
            
        # Explicitly connect Background to World Output
        world.node_tree.links.new(bg_node.outputs['Background'], output_node.inputs['Surface'])

        # Ensure no texture is linked to the color input (overwrite existing environment map)
        if bg_node.inputs['Color'].is_linked:
            for link in bg_node.inputs['Color'].links:
                world.node_tree.links.remove(link)

        # Randomize Color
        # Hue: Random
        # Saturation: Very limited (0.0 - 0.3)
        # Value: Not too bright (0.05 - 0.3)
        h = self.rng.random()
        s = self.rng.uniform(0.0, 0.3)
        v = self.rng.uniform(0.05, 0.4)
        color_rgb = self.hsv_to_rgb(h, s, v)
        
        bg_node.inputs['Color'].default_value = (*color_rgb, 1.0) # RGBA
        
        # Randomize Strength
        strength = self.rng.uniform(0.1, 0.5)
        bg_node.inputs['Strength'].default_value = strength

    def configure_light_linking(self, light_obj: bpy.types.Object):
        """
        Configure light linking for a given light object to exclude objects in the excluded collection.
        
        Args:
            light_obj: The light object to configure
        """
        if not self.excluded_collection_name or self.excluded_collection_name not in bpy.data.collections:
            return
        
        excluded_col = bpy.data.collections[self.excluded_collection_name]
        bpy.context.view_layer.objects.active = light_obj # Select the light as the active object
        bpy.ops.object.light_linking_receiver_collection_new() # Initialize light linking for the light
        
        def get_collection_name(light_object_name):
            possible_collections = [col for col in bpy.data.collections if col.name.startswith("Light Linking for " + light_object_name)]
            if possible_collections:
                return sorted([collection.name for collection in possible_collections])[-1] # Return the last one alphabetically (most recently created)
            return None

        light_linking_collection_name = get_collection_name(light_obj.name)
        lighting_linking_collection = bpy.data.collections.get(light_linking_collection_name)
        if lighting_linking_collection:
            for object_to_exclude in excluded_col.objects:
                lighting_linking_collection.objects.link(object_to_exclude) 
            
            for object in lighting_linking_collection.collection_objects:
                object.light_linking.link_state = 'EXCLUDE'

    def generate_light_configuration(self, seed=None):
        if seed is not None:
            self.set_seed(seed)

        self.clear_previous_lights()
        self.randomize_background()
        light_collection = self._get_light_collection()
        num_lights = self.rng.randint(self.min_lights, self.max_lights)

        
        # We define the "Up" direction for the hemisphere.
        # Using Global Z (0,0,1) helps to avoid intersecting the floor.
        cone_axis = Vector((0, 0, 1)) 

        print(f"Generating {num_lights} lights in a {self.max_cone_angle} degree cone...", flush=True)
        
        for i in range(num_lights):
            # 1. Random Props (use per-instance RNG)
            dist = self.rng.uniform(self.min_dist, self.max_dist)
            print("CHOSE DISTANCE OF:", dist, flush=True)
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

            # Configure Light Linking if excluded collection is specified
            self.configure_light_linking(light_obj)
                
            light_obj.location = local_pos
            light_data.energy = power
            light_data.color = color_rgb
            light_data.shape = 'SQUARE'
            light_data.size = size

            # 4. Point Light at origin
            direction = Vector((0, 0, 0)) - light_obj.location
            light_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

            self.light_objects.append(light_obj)

        print("Light generation complete.", flush=True)
    
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
    
    def check_object_obstructs_lighting(self, candidate_obj: bpy.types.Object, target_obj: bpy.types.Object) -> bool:
        """
        Check if a candidate object obstructs visibility from any light to the target object.
        
        Args:
            candidate_obj: The object to check for obstruction
            target_obj: The focus object that must remain visible to all lights
            
        Returns:
            True if the candidate object obstructs any light, False otherwise
        """
        bpy.context.view_layer.update()
        
        scene = bpy.context.scene
        depsgraph = bpy.context.evaluated_depsgraph_get()
        target_center = target_obj.matrix_world.translation
        
        for light_obj in self.light_objects:
            light_pos = light_obj.location
            direction = target_center - light_pos
            dist = direction.length
            
            if dist < 1e-4:
                continue
            
            # Cast ray from light to target
            success, location, normal, index, hit_object, matrix = scene.ray_cast(
                depsgraph, light_pos, direction.normalized(), distance=dist
            )
            
            # If we hit the candidate object before reaching the target, it's obstructing
            if success and hit_object == candidate_obj:
                print(f"Object {candidate_obj.name} obstructs light {light_obj.name} to target {target_obj.name}")
                return True
        
        return False