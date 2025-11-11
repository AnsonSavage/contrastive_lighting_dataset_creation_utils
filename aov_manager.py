from abc import ABC, abstractmethod
import os
import bpy  # type: ignore

class AOVNodeManager:
    """Helper class responsible for low-level node creation and shader tree traversal.

    This isolates node types, socket name usage, and location bookkeeping from the
    higher-level AOV configuration logic.
    """

    def __init__(self, input_name: str, fallback_values: dict, logger):
        self.input_name = input_name
        self.fallback = fallback_values
        self.log = logger  # callable(str)

    # ---- Node creation primitives ----
    def make_value(self, nt, val, loc=(0, 0)):
        n = nt.nodes.new("ShaderNodeValue")
        n.outputs[0].default_value = float(val)
        n.location = loc
        return n, n.outputs[0]

    def coerce_to_float(self, nt, sock, loc=(0, 0)):
        st = getattr(sock, "type", "")
        if st == 'VALUE':
            return sock
        if st == 'RGBA':
            n = nt.nodes.new("ShaderNodeRGBToBW")
            n.location = (loc[0] - 40, loc[1])
            nt.links.new(n.inputs['Color'], sock)
            return n.outputs['Val']
        if st == 'VECTOR':
            n = nt.nodes.new("ShaderNodeVectorMath")
            n.operation = 'LENGTH'
            n.location = (loc[0] - 40, loc[1])
            nt.links.new(n.inputs[0], sock)
            return n.outputs['Value']
        self.log(f"Using fallback value {self.fallback['unsupported']} for unsupported socket type: {st}")
        v, out = self.make_value(nt, self.fallback['unsupported'], (loc[0] - 120, loc[1]))
        return out

    def make_math(self, nt, op, a, b, clamp=False, loc=(0, 0)):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        n.location = loc
        nt.links.new(n.inputs[0], a)
        nt.links.new(n.inputs[1], b)
        return n, n.outputs[0]

    def mix_float(self, nt, fac, a, b, clamp=True, loc=(0, 0)):
        fac = self.coerce_to_float(nt, fac, (loc[0] - 160, loc[1] + 20))
        try:
            n = nt.nodes.new("ShaderNodeMix")
            n.data_type = 'FLOAT'
            n.clamp_result = clamp
            n.clamp_factor = False
            n.location = loc
            nt.links.new(n.inputs['Factor'], fac)
            nt.links.new(n.inputs['A'], a)
            nt.links.new(n.inputs['B'], b)
            return n, n.outputs['Result']
        except Exception as e:
            self.log(f"Fallback mix_float implementation used due to: {e}")
            one = nt.nodes.new("ShaderNodeValue")
            one.outputs[0].default_value = 1.0
            one.location = (loc[0] - 220, loc[1] - 40)
            inv_node, inv = self.make_math(nt, 'SUBTRACT', one.outputs[0], fac, False, (loc[0] - 160, loc[1] - 40))
            a_mul_node, a_mul = self.make_math(nt, 'MULTIPLY', a, inv, False, (loc[0] - 100, loc[1] - 40))
            b_mul_node, b_mul = self.make_math(nt, 'MULTIPLY', b, fac, False, (loc[0] - 40, loc[1] - 10))
            add_node, out = self.make_math(nt, 'ADD', a_mul, b_mul, clamp, (loc[0] + 20, loc[1] - 20))
            return add_node, out

    # ---- Graph helpers ----
    def active_material_output(self, nt):
        outs = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
        for n in outs:
            if getattr(n, "is_active_output", False):
                return n
        return outs[0] if outs else None

    def socket_source(self, sock):
        return sock.links[0].from_socket if sock and sock.is_linked and sock.links else None

    def extract_input_from_bsdf(self, nt, bsdf_node, loc=(0, 0)):
        input_name = self.input_name
        if input_name in bsdf_node.inputs:
            inp = bsdf_node.inputs[input_name]
            if inp.is_linked:
                src = inp.links[0].from_socket
                return self.coerce_to_float(nt, src, (loc[0] - 120, loc[1]))
            v, out = self.make_value(nt, getattr(inp, "default_value", 0.5), (loc[0] - 120, loc[1]))
            return out
        if bsdf_node.bl_idname == "ShaderNodeBsdfTransparent":
            self.log(f"Using fallback value {self.fallback['transparent']} for Transparent BSDF (no '{input_name}' input)")
            v, out = self.make_value(nt, self.fallback['transparent'], (loc[0] - 120, loc[1]))
            return out
        if bsdf_node.bl_idname == "ShaderNodeEmission":
            self.log(f"Using fallback value {self.fallback['emission']} for Emission shader (no '{input_name}' input)")
            v, out = self.make_value(nt, self.fallback['emission'], (loc[0] - 120, loc[1]))
            return out
        self.log(f"Using fallback value {self.fallback['unsupported']} for {bsdf_node.bl_idname} (no '{input_name}' input)")
        v, out = self.make_value(nt, self.fallback['unsupported'], (loc[0] - 120, loc[1]))
        return out

    def build_scalar_param_tree(self, nt, shader_sock, visited, loc=(0, 0)):
        if shader_sock is None:
            self.log(f"Using fallback value {self.fallback['unsupported']} for None socket")
            v, out = self.make_value(nt, self.fallback['unsupported'], loc)
            return out

        key = (shader_sock.node.name, shader_sock.name)
        if key in visited:
            self.log(f"Using fallback value {self.fallback['visited_node']} for already visited node: {shader_sock.node.name}")
            v, out = self.make_value(nt, self.fallback['visited_node'], loc)
            return out
        visited.add(key)

        node = shader_sock.node
        bl_id = getattr(node, 'bl_idname', '')

        if bl_id in {"ShaderNodeBsdfPrincipled", "ShaderNodeBsdfGlossy", "ShaderNodeBsdfDiffuse",
                     "ShaderNodeBsdfRefraction", "ShaderNodeBsdfGlass"}:
            return self.extract_input_from_bsdf(nt, node, loc)

        if bl_id == "ShaderNodeMixShader":
            f_in = node.inputs[0]
            f_src = self.socket_source(f_in)
            if f_src is None:
                default_val = getattr(f_in, "default_value", self.fallback['default_factor'])
                self.log(f"Using default/fallback value {default_val} for unlinked Mix Shader factor")
                v, f_src = self.make_value(nt, default_val, (loc[0] - 240, loc[1] + 60))
            f_src = self.coerce_to_float(nt, f_src, (loc[0] - 200, loc[1] + 60))

            a_sock = self.socket_source(node.inputs[1])
            b_sock = self.socket_source(node.inputs[2])

            a_val = self.build_scalar_param_tree(nt, a_sock, visited, (loc[0] - 140, loc[1] + 120))
            b_val = self.build_scalar_param_tree(nt, b_sock, visited, (loc[0] - 140, loc[1] - 0))

            mix_node, mix_out = self.mix_float(nt, f_src, a_val, b_val, clamp=True, loc=loc)
            return mix_out

            
        if bl_id == "ShaderNodeAddShader":
            a_sock = self.socket_source(node.inputs[0])
            b_sock = self.socket_source(node.inputs[1])
            a_val = self.build_scalar_param_tree(nt, a_sock, visited, (loc[0] - 140, loc[1] + 60))
            b_val = self.build_scalar_param_tree(nt, b_sock, visited, (loc[0] - 140, loc[1] - 60))
            add_node, add_out = self.make_math(nt, 'ADD', a_val, b_val, clamp=True, loc=loc)
            return add_out

        # Groups/Volumes/other closures: conservative fallback
        self.log(f"Using fallback value {self.fallback['unsupported']} for unsupported node type: {bl_id}")
        v, out = self.make_value(nt, self.fallback['unsupported'], (loc[0] - 120, loc[1]))
        return out

    def ensure_aov_output_node(self, nt, pass_name, loc=(1200, 0)):
        for n in nt.nodes:
            if n.bl_idname == "ShaderNodeOutputAOV" and getattr(n, "aov_name", "") == pass_name:
                return n
        n = nt.nodes.new("ShaderNodeOutputAOV")
        n.aov_name = pass_name
        n.location = loc
        return n
    
    def get_nodes_by_type(self, node_tree, node_type):
        return [n for n in node_tree.nodes if n.bl_idname == node_type]
    

    def get_aov_output_from_compositing_node(self, node_tree, pass_name):
        try:
            compositing_node = self.get_nodes_by_type(node_tree, "CompositorNodeRLayers")[0]
        except IndexError:
            # Add the compositing node if it doesn't exist
            compositing_node = node_tree.nodes.new("CompositorNodeRLayers")

        return compositing_node.outputs.get(pass_name)
    
    def add_file_output_node(self, node_tree, output_path, input_socket):
        file_output_node = node_tree.nodes.new("CompositorNodeOutputFile")
        file_output_node.base_path = output_path
        file_output_node.location = (400, 0)
        file_output_node.format.color_management = 'OVERRIDE'
        file_output_node.format.color_mode = 'RGB'
        file_output_node.format.view_settings.view_transform = 'Standard'

        node_tree.links.new(file_output_node.inputs[0], input_socket)
        return file_output_node

class AOVManager(ABC):
    def __init__(self, input_name: str, output_directory: str):
        self.input_name = input_name
        self.pass_name = input_name  # pass name assumed same as input name
        self.output_directory = output_directory
        self.node_manager = AOVNodeManager(self.input_name, {}, self.log)

    def log(self, msg: str):
        print(f"[AOV Builder:{self.pass_name}] {msg}")

    def _configure_file_output(self, scene, pass_name, output_path):
        scene.use_nodes = True # Enable compositing nodes if not already enabled
        aov_output = self.node_manager.get_aov_output_from_compositing_node(scene.node_tree, pass_name)
        assert aov_output is not None, f"AOV output '{pass_name}' not found in compositing nodes."
        self.node_manager.add_file_output_node(scene.node_tree, output_path, aov_output)
    
    def apply(self):
        if os.path.exists(self._get_output_path()):
            self.log(f"Output path {self._get_output_path()} already exists, not reconfiguring.")
            return
        self._configure_for_aov()
        self._configure_file_output(bpy.context.scene, self.pass_name, self._get_output_path())
        self.log(f"Shader AOV '{self.pass_name}' ready.")
    
    def _get_output_path(self) -> str:
        return os.path.join(self.output_directory, f"{self._get_output_name().lower()}.png")
    
    @abstractmethod
    def _configure_for_aov(self):
        pass

    @abstractmethod
    def _get_output_name(self) -> str:
        pass


class AlbedoAOVManager(AOVManager):
    def __init__(self, output_directory: str):
        super().__init__(input_name="DiffCol", output_directory=output_directory)
    
    def _configure_for_aov(self):
        # set use_pass_diffuse_color to True on the view layer
        view_layer = bpy.context.view_layer
        view_layer.use_pass_diffuse_color = True
        self.log("Enabled Diffuse Color pass on view layer.")
    
    def _get_output_name(self):
        return "albedo"

class NonDefaultAOVManager(AOVManager):
    """Refactors previous procedural script into a class-based interface.

    Usage:
        builder = ConfigureMaterialsForAOV(input_name="Roughness")
        builder.run()  # ensures AOV exists and wires all materials
    """
    DEFAULT_FALLBACKS = {
        'unsupported': 0.5,
        'emission': 0.0,
        'transparent': 0.0,
        'default_factor': 0.5,
        'visited_node': 0.5,
    }

    def __init__(self, input_name: str, output_directory: str, fallback_values: dict | None = None):
        super().__init__(input_name, output_directory)
        self.fallback = {**self.DEFAULT_FALLBACKS, **(fallback_values or {})}

    # --- View layer helpers ---
    def _ensure_view_layer_shader_aov(self, view_layer, name, data_type='VALUE'):
        for a in view_layer.aovs:
            if a.name == name:
                a.type = data_type
                return a
        a = view_layer.aovs.add()
        a.name = name
        a.type = data_type
        return a

    # --- Material processing ---
    def _process_material(self, mat) -> bool:
        if not mat or not mat.use_nodes or not mat.node_tree:
            return False
        node_tree = mat.node_tree
        out = self.node_manager.active_material_output(node_tree)
        if not out:
            return False
        surface_in = out.inputs.get('Surface', None)
        src = self.node_manager.socket_source(surface_in)
        visited = set()
        param_socket = self.node_manager.build_scalar_param_tree(node_tree, src, visited, (800, 0))
        aov_node = self.node_manager.ensure_aov_output_node(node_tree, self.pass_name, (1100, 0))
        try:
            node_tree.links.new(aov_node.inputs['Value'], param_socket)
        except Exception:
            # fallback for older Blender versions or index-based access
            node_tree.links.new(aov_node.inputs[1], param_socket)
        return True
    
    def _configure_for_aov(self):
        self._ensure_view_layer_shader_aov(bpy.context.view_layer, self.pass_name, 'VALUE')
        count = 0
        for mat in bpy.data.materials:
            try:
                if self._process_material(mat):
                    count += 1
            except Exception as e:
                self.log(f"Skipped {mat.name}: {e}")
        self.log(f"Updated {count} materials.")
    
    def _get_output_name(self):
        return self.input_name
        
def get_aov_manager_factory(input_name: str, output_directory: str) -> AOVManager:
    if input_name.lower() == "albedo":
        return AlbedoAOVManager(output_directory=output_directory)
    elif input_name.lower() in ("roughness", "metallic"):
        return NonDefaultAOVManager(input_name=input_name.title(), output_directory=output_directory)
    else:
        raise ValueError(f"Unsupported AOV input name: {input_name}")

def configure_aovs(input_names: list[str], output_directory: str) -> None:
    for name in input_names:
        builder = get_aov_manager_factory(name, output_directory)
        builder.apply()