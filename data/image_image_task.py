import os
import random
import base64
import pickle
from environment import BLENDER_PATH, DATA_PATH
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import HDRIName
from .signature_vector.invariant_attributes import SceneID, CameraSeed
from .signature_vector.data_getters import HDRIData, OutdoorSceneData
import subprocess
from concurrent_tasks_helper import ConcurrentTasksHelper

# TODO: We'll need to do some thinking for how to organize all of these classes better :)

image_image_rng = random.Random(0)

class ImageImageRenderGenerator:
    def __init__(self):
        self.path_to_blender = BLENDER_PATH

    def do_render(self, signature_vector: SignatureVector, output_path: str, headless: bool = True) -> str:
        scene_path = OutdoorSceneData().get_scene_path_by_id(signature_vector.invariant_attributes[0].scene_id)
        try:
            result = subprocess.run([
                self.path_to_blender,
                scene_path,
                '--background' if headless else '',
                '--python', 'render_manager.py',
                
                '--', # Begin command line args for the script
                '--mode=image-image',
                f'--output_path={output_path}',
                f'--serialized_signature_vector={base64.b64encode(pickle.dumps(signature_vector)).decode("ascii")}',
            ],
            capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            print("Error during Blender rendering:")
            print(e.stdout.decode('utf-8'))
            print(e.stderr.decode('utf-8'))
            raise e


        for line in result.stdout.splitlines():
            if '[render_manager]' in line.decode('utf-8'):
                print(line.decode('utf-8'))
        if result.stderr:
            print("Blender script errors: ", result.stderr)
        return output_path

    def do_render_batch_for_scene(self, signature_vectors: list[SignatureVector], output_paths: list[str], headless: bool = True) -> list[str]:
        """Render multiple images for the same scene in a single Blender process.

        All signature_vectors must share the same scene_id.
        """
        if not signature_vectors:
            return []
        scene_id = signature_vectors[0].invariant_attributes[0].scene_id
        # Validate all are same scene
        for sv in signature_vectors:
            if sv.invariant_attributes[0].scene_id != scene_id:
                raise ValueError("All signature vectors in batch must have the same scene_id")
        if len(signature_vectors) != len(output_paths):
            raise ValueError("signature_vectors and output_paths must have the same length")

        scene_path = OutdoorSceneData().get_scene_path_by_id(scene_id)
        serialized_svs = base64.b64encode(pickle.dumps(signature_vectors)).decode('ascii')
        serialized_paths = base64.b64encode(pickle.dumps(output_paths)).decode('ascii')
        try:
            result = subprocess.run([
                self.path_to_blender,
                scene_path,
                '--background' if headless else '',
                '--python', 'render_manager.py',
                '--',
                '--mode=image-image-batch',
                f'--serialized_signature_vectors={serialized_svs}',
                f'--serialized_output_paths={serialized_paths}',
            ], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            print("Error during Blender batch rendering:")
            print(e.stdout.decode('utf-8'))
            print(e.stderr.decode('utf-8'))
            raise e

        for line in result.stdout.splitlines():
            if '[render_manager]' in line.decode('utf-8'):
                print(line.decode('utf-8'))
        if result.stderr:
            print("Blender script errors: ", result.stderr)
        return output_paths

class ImageImageSignatureVector(SignatureVector):
    def __init__(self, variant_attributes: tuple[HDRIName], invariant_attributes: tuple[SceneID, CameraSeed]):
        super().__init__(variant_attributes, invariant_attributes)
    def to_path(self):
        # Build path relative to DATA_PATH/renders (future substructure could be added)
        base_data_path = os.path.join(DATA_PATH, 'renders')
        path = os.path.join(
            base_data_path,
            self.variant_attributes[0].name, # HDRI name
            f"hdri-offset_{self.variant_attributes[0].z_rotation_offset_from_camera}_camera_{self.invariant_attributes[1].seed}_{self.invariant_attributes[0].scene_id.replace('.blend', '')}.png"
        )
        if not os.path.exists(path):
            ImageImageRenderGenerator().do_render(self, path)
        return path

class ImageImageDataLoader:
    def get_batch_of_signature_vectors(self, invariant_free_mask, batch_size:int = None) -> list[tuple[ImageImageSignatureVector, ImageImageSignatureVector]]: # normally would also include a variant free mask, but this is true trivially in this case.
        # If batch_size is none, should it get the biggest batch size it can?
        # So, basically what we need to do now is:
        """
        - If the SceneID is not free, we need to select a single random scene
        - Similarly, if the CameraSeed is not free, we need to select a single random camera seed

        # Otherwise, we sample those with replacement

        - The HDRI name will always be free, so we can just sample that without replacement
        """

        # TODO: you should probably also do some digging into whether you can support multiple positive pairs in your batch.
        # For now, we're just going to have one positive pair per batch.
        # TODO: Once you add support for rejection sampling, etc. you can do the same kind of sampling here that you do in the image_text_instructions_task.py file.

        available_scenes = OutdoorSceneData().get_available_scene_ids()
        available_hdris = HDRIData.get_available_hdris_names()
        # print("Available scenes:", available_scenes)
        # print("Available HDRIs:", available_hdris)
        selection_of_hdris = image_image_rng.sample(available_hdris, k=batch_size)
        rotations = [image_image_rng.randint(0, 360) for _ in range(batch_size)]
        selected_scene_left = image_image_rng.choice(available_scenes)
        selected_scene_right = image_image_rng.choice(available_scenes)
        camera_seed_left = image_image_rng.randint(0, 1e6)
        camera_seed_right = image_image_rng.randint(0, 1e6)

        batch = []
        for i in range(batch_size):
            selected_hdri = selection_of_hdris[i]
            selected_rotation = rotations[i]
            hdri_attribute = HDRIName(
                name=selected_hdri,
                z_rotation_offset_from_camera=selected_rotation
            )

            signature_vector_left = ImageImageSignatureVector(
                variant_attributes=(hdri_attribute,),
                invariant_attributes=(
                    SceneID(scene_id=selected_scene_left),
                    CameraSeed(seed=camera_seed_left)
                )
            )

            signature_vector_right = ImageImageSignatureVector(
                variant_attributes=(hdri_attribute,),
                invariant_attributes=(
                    SceneID(scene_id=selected_scene_right),
                    CameraSeed(seed=camera_seed_right)
                )
            )
            batch.append((signature_vector_left, signature_vector_right))
        return batch


    def get_batch_of_images_given_signature_vectors(self, signature_vectors: list[tuple[ImageImageSignatureVector, ImageImageSignatureVector]], shard_index=0, shard_count=1) -> list[tuple[str, str]]:
        """Resolve images for a batch, rendering missing ones.

        Optimization: group by scene_id and render all images for a scene in one Blender run.
        """
        # Helper to compute path (without rendering)
        def compute_path(sv: ImageImageSignatureVector) -> str:
            base_data_path = os.path.join(DATA_PATH, 'renders')
            return os.path.join(
                base_data_path,
                sv.variant_attributes[0].name,
                f"hdri-offset_{sv.variant_attributes[0].z_rotation_offset_from_camera}_camera_{sv.invariant_attributes[1].seed}_{sv.invariant_attributes[0].scene_id.replace('.blend', '')}.png"
            )

        # Build lists and find which are missing
        left_paths, right_paths = [], []
        all_to_render_by_scene: dict[str, list[ImageImageSignatureVector]] = {}
        all_output_paths_by_scene: dict[str, list[str]] = {}

        # completed_renders = []
        for sv_left, sv_right in signature_vectors:
            left_path = compute_path(sv_left)
            right_path = compute_path(sv_right)
            left_paths.append(left_path)
            right_paths.append(right_path)

            for sv, p in ((sv_left, left_path), (sv_right, right_path)):
                if os.path.exists(p):
                    # completed_renders.append(p)
                    continue
                scene_id = sv.invariant_attributes[0].scene_id
                all_to_render_by_scene.setdefault(scene_id, []).append(sv)
                all_output_paths_by_scene.setdefault(scene_id, []).append(p)

        # Render per-scene in batches
        renderer = ImageImageRenderGenerator()
        scene_ids = sorted(all_to_render_by_scene.keys())
        concurrent_helper = ConcurrentTasksHelper(shard_index, shard_count, scene_ids, already_completed_tasks=set())
        while scene_id := concurrent_helper.get_next_task():
            all_signature_vectors_for_given_scene = all_to_render_by_scene[scene_id]
            outs = all_output_paths_by_scene[scene_id]
            # Ensure directories exist
            for outp in outs:
                os.makedirs(os.path.dirname(outp), exist_ok=True)
            print(f"Currently rendering all images for scene {scene_id} in batch of size {len(all_signature_vectors_for_given_scene)}")
            renderer.do_render_batch_for_scene(all_signature_vectors_for_given_scene, outs)

        # Return paths in original order
        return list(zip(left_paths, right_paths))
