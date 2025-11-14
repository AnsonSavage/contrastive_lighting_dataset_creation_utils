import os
import random
import pickle
from environment import BLENDER_PATH, DATA_PATH
from .signature_vector.signature_vector import SignatureVector
from .signature_vector.light_attribute import HDRIName
from .signature_vector.invariant_attributes import SceneID, CameraSeed
from .signature_vector.data_getters import HDRIData, OutdoorSceneData
import subprocess
from concurrent_tasks_helper import ConcurrentTasksHelper
from .temp_payload import temporary_payload_file

# TODO: We'll need to do some thinking for how to organize all of these classes better :)

class ImageImageRenderGenerator:
    def __init__(self):
        self.path_to_blender = BLENDER_PATH

    def do_render(self, signature_vector: 'ImageImageSignatureVector', output_path: str, headless: bool = True) -> str:
        scene_path = OutdoorSceneData().get_scene_path_by_id(signature_vector.get_scene_id())
        payload = pickle.dumps(signature_vector)
        try:
            print("Rendering image to", output_path, flush=True)
            with temporary_payload_file(payload) as payload_path:
                cmd = [
                    self.path_to_blender,
                    scene_path,
                    '--background' if headless else '',
                    '--python', 'render_manager.py',
                    '--',
                    '--mode=image-image',
                    f'--output_path={output_path}',
                    f'--serialized_signature_vector_path={payload_path}',
                    '--aovs', 'metallic', 'albedo', 'roughness',
                ]
                cmd = [arg for arg in cmd if arg]
                result = subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            print("Error during Blender rendering:", flush=True)
            print(e.stdout.decode('utf-8'), flush=True)
            print(e.stderr.decode('utf-8'), flush=True)
            raise e

        for line in result.stdout.splitlines():
            if '[render_manager]' in line.decode('utf-8'):
                print(line.decode('utf-8'))
        if result.stderr:
            print("Blender script errors: ", result.stderr, flush=True)

        return output_path

    def do_render_batch_for_scene(self, signature_vectors: list['ImageImageSignatureVector'], output_paths: list[str], headless: bool = True) -> list[str]:
        """Render multiple images for the same scene in a single Blender process.

        All signature_vectors must share the same scene_id.
        """
        if not signature_vectors:
            return []
        scene_id = signature_vectors[0].get_scene_id()
        # Validate all are same scene
        for sv in signature_vectors:
            if sv.get_scene_id() != scene_id:
                raise ValueError("All signature vectors in batch must have the same scene_id")
        if len(signature_vectors) != len(output_paths):
            raise ValueError("signature_vectors and output_paths must have the same length")

        scene_path = OutdoorSceneData().get_scene_path_by_id(scene_id)
        serialized_svs = pickle.dumps(signature_vectors)
        serialized_paths = pickle.dumps(output_paths)
        try:
            with temporary_payload_file(serialized_svs) as sv_path, temporary_payload_file(serialized_paths) as paths_path:
                cmd = [
                    self.path_to_blender,
                    scene_path,
                    '--background' if headless else '',
                    '--python', 'render_manager.py',
                    '--',
                    '--mode=image-image-batch',
                    f'--serialized_signature_vectors_path={sv_path}',
                    f'--serialized_output_paths_path={paths_path}',
                    '--aovs', 'metallic', 'albedo', 'roughness',
                ]
                cmd = [arg for arg in cmd if arg]
                result = subprocess.run(cmd, capture_output=True, check=True)
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
            self.get_hdri_name(),
            f"hdri-offset_{self.get_hdri_rotation()}_camera_{self.get_camera_seed()}_{self.get_scene_id()}.png"
        )
        if not os.path.exists(path):
            ImageImageRenderGenerator().do_render(self, path)
        return path
    
    def get_hdri_name(self) -> str:
        return self.variant_attributes[0].name
    def get_camera_seed(self) -> int:
        return self.invariant_attributes[1].seed
    def get_scene_id(self) -> str:
        return self.invariant_attributes[0].scene_id.replace('.blend', '')
    def get_hdri_rotation(self) -> int:
        return self.variant_attributes[0].z_rotation_offset_from_camera

class ImageImageDataLoader:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

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
        selection_of_hdris = self.rng.sample(available_hdris, k=batch_size)
        rotations = [self.rng.randint(0, 360) for _ in range(batch_size)]
        selected_scene_left = self.rng.choice(available_scenes)
        selected_scene_right = self.rng.choice(available_scenes)
        camera_seed_left = self.rng.randint(0, 1e6)
        camera_seed_right = self.rng.randint(0, 1e6)

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


    def get_batch_of_images_given_signature_vectors(self, signature_vectors: list[tuple[ImageImageSignatureVector, ImageImageSignatureVector]], shard_index=0, shard_count=1, task_method='split_by_scene') -> list[tuple[str, str]]:
        """Resolve images for a batch, rendering missing ones.

        Optimization: group by scene_id and render all images for a scene in one Blender run.
        """
        # Helper to compute path (without rendering)
        def compute_path(sv: ImageImageSignatureVector) -> str:
            base_data_path = os.path.join(DATA_PATH, 'renders')
            return os.path.join(
                base_data_path,
                sv.get_hdri_name(),
                f"hdri-offset_{sv.get_hdri_rotation()}_camera_{sv.get_camera_seed()}_{sv.get_scene_id()}.png"
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
                scene_id = sv.get_scene_id()
                all_to_render_by_scene.setdefault(scene_id, []).append(sv)
                all_output_paths_by_scene.setdefault(scene_id, []).append(p)

        # Render per-scene in batches
        renderer = ImageImageRenderGenerator()
        
        if task_method == 'split_by_scene': # This one tends to be more efficient when many images from one scene will be rendered, that way a blender file with one scene can be loaded and multiple renders can be saved from it.
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
        
        elif task_method == 'individual':
            all_signature_vectors = []
            all_output_paths = []
            for scene_id in all_to_render_by_scene:
                all_signature_vectors.extend(all_to_render_by_scene[scene_id])
                all_output_paths.extend(all_output_paths_by_scene[scene_id])
            already_completed_tasks = set([p for p in all_output_paths if os.path.exists(p)])
            print(len(already_completed_tasks), "renders already completed out of", len(all_output_paths), flush=True)
            concurrent_helper = ConcurrentTasksHelper(shard_index, shard_count, all_output_paths, already_completed_tasks=already_completed_tasks)
            while output_path := concurrent_helper.get_next_task():
                print("Next output path to render:", output_path, flush=True)
                idx = all_output_paths.index(output_path)
                sv = all_signature_vectors[idx]
                # Ensure directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                print(f"Rendering individual image {output_path}")
                renderer.do_render(sv, output_path)
        
        else:
            raise ValueError(f"Unknown task method {task_method}")

        # Return paths in original order
        return list(zip(left_paths, right_paths))
