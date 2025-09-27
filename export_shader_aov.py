import bpy

# Configure these two names per use case:
PASS_NAME  = "Roughness"   # The View Layer Shader AOV name to write into (shown in passes/compositor)
INPUT_NAME = "Roughness"   # The BSDF input name to extract and mix across the shader tree

# Fallback constants for nodes that lack the requested INPUT_NAME
FALLBACK_UNSUPPORTED  = 0.5
FALLBACK_EMISSION     = 0.0
FALLBACK_TRANSPARENT  = 0.0

# --- View Layer / AOV helpers ---

def ensure_view_layer_shader_aov(view_layer, name, data_type='VALUE'):
    """
    Ensure a Shader AOV with the given name exists on the active View Layer.
    Uses ViewLayer.aovs.add() per current API.
    """
    for a in view_layer.aovs:
        if a.name == name:
            a.type = data_type
            return a
    a = view_layer.aovs.add()
    a.name = name
    a.type = data_type
    return a

# --- Node-building utilities ---

def make_value(nt, val, loc=(0,0)):
    """Create a Value node initialized to val and return its output socket."""
    n = nt.nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = float(val)
    n.location = loc
    return n, n.outputs[0]

def coerce_to_float(nt, sock, loc=(0,0)):
    """
    Convert an input socket of type RGBA or VECTOR to a single float so it can
    be mixed numerically; VALUE passes through unchanged.
    """
    st = getattr(sock, "type", "")
    if st == 'VALUE':
        return sock
    if st == 'RGBA':
        n = nt.nodes.new("ShaderNodeRGBToBW")
        n.location = (loc[0]-40, loc[1])
        nt.links.new(n.inputs['Color'], sock)
        return n.outputs['Val']
    if st == 'VECTOR':
        n = nt.nodes.new("ShaderNodeVectorMath")
        n.operation = 'LENGTH'
        n.location = (loc[0]-40, loc[1])
        nt.links.new(n.inputs[0], sock)
        return n.outputs['Value']
    v, out = make_value(nt, FALLBACK_UNSUPPORTED, (loc[0]-120, loc[1]))
    return out

def make_math(nt, op, a, b, clamp=False, loc=(0,0)):
    """Create a Math node with two inputs linked and return its output."""
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    n.location = loc
    nt.links.new(n.inputs[0], a)
    nt.links.new(n.inputs[1], b)
    return n, n.outputs[0]

def mix_float(nt, fac, a, b, clamp=True, loc=(0,0)):
    """
    Interpolate two float values with Factor, matching Blender’s Mix FLOAT behavior.
    """
    fac = coerce_to_float(nt, fac, (loc[0]-160, loc[1]+20))
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
    except:
        one = nt.nodes.new("ShaderNodeValue"); one.outputs[0].default_value = 1.0; one.location = (loc[0]-220, loc[1]-40)
        inv_node, inv = make_math(nt, 'SUBTRACT', one.outputs[0], fac, False, (loc[0]-160, loc[1]-40))
        a_mul_node, a_mul = make_math(nt, 'MULTIPLY', a, inv, False, (loc[0]-100, loc[1]-40))
        b_mul_node, b_mul = make_math(nt, 'MULTIPLY', b, fac, False, (loc[0]-40, loc[1]-10))
        add_node, out = make_math(nt, 'ADD', a_mul, b_mul, clamp, (loc[0]+20, loc[1]-20))
        return add_node, out

# --- Shader graph traversal ---

def active_material_output(nt):
    """Prefer the active Material Output; fall back to any output if needed."""
    outs = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    for n in outs:
        if getattr(n, "is_active_output", False):
            return n
    return outs[0] if outs else None

def socket_source(sock):
    """Return the from_socket if the socket is linked; else None."""
    return sock.links[0].from_socket if sock and sock.is_linked and sock.links else None

def extract_input_from_bsdf(nt, bsdf_node, input_name, loc=(0,0)):
    """
    Return a FLOAT socket representing the requested BSDF input:
    - If the BSDF exposes 'input_name', follow the link or use its default value.
    - Provide sensible fallbacks for closures that have no such parameter.
    """
    if input_name in bsdf_node.inputs:
        inp = bsdf_node.inputs[input_name]
        if inp.is_linked:
            src = inp.links[0].from_socket
            return coerce_to_float(nt, src, (loc[0]-120, loc[1]))
        v, out = make_value(nt, getattr(inp, "default_value", 0.5), (loc[0]-120, loc[1]))
        return out
    if bsdf_node.bl_idname == "ShaderNodeBsdfTransparent":
        v, out = make_value(nt, FALLBACK_TRANSPARENT, (loc[0]-120, loc[1]))
        return out
    if bsdf_node.bl_idname == "ShaderNodeEmission":
        v, out = make_value(nt, FALLBACK_EMISSION, (loc[0]-120, loc[1]))
        return out
    v, out = make_value(nt, FALLBACK_UNSUPPORTED, (loc[0]-120, loc[1]))
    return out

def build_scalar_param_tree(nt, shader_sock, input_name, visited, loc=(0,0)):
    """
    Recursively approximate a single FLOAT describing 'input_name' across the shader tree:
    - For BSDF nodes: read the requested input (linked or default).
    - For Mix Shader: recursively compute A/B and interpolate by the same Factor.
    - For Add Shader: add child values and clamp to [0,1] as a pragmatic bound.
    """
    if shader_sock is None:
        v, out = make_value(nt, FALLBACK_UNSUPPORTED, loc)
        return out

    key = (shader_sock.node.name, shader_sock.name)
    if key in visited:
        v, out = make_value(nt, FALLBACK_UNSUPPORTED, loc)
        return out
    visited.add(key)

    node = shader_sock.node
    bl_id = getattr(node, 'bl_idname', '')

    if bl_id in {"ShaderNodeBsdfPrincipled", "ShaderNodeBsdfGlossy", "ShaderNodeBsdfDiffuse",
                 "ShaderNodeBsdfRefraction", "ShaderNodeBsdfGlass"}:
        return extract_input_from_bsdf(nt, node, input_name, loc)

    if bl_id == "ShaderNodeMixShader":
        f_in = node.inputs[0]
        f_src = socket_source(f_in)
        if f_src is None:
            v, f_src = make_value(nt, getattr(f_in, "default_value", 0.5), (loc[0]-240, loc[1]+60))
        f_src = coerce_to_float(nt, f_src, (loc[0]-200, loc[1]+60))

        a_sock = socket_source(node.inputs[1])
        b_sock = socket_source(node.inputs[2])

        a_val = build_scalar_param_tree(nt, a_sock, input_name, visited, (loc[0]-140, loc[1]+120))
        b_val = build_scalar_param_tree(nt, b_sock, input_name, visited, (loc[0]-140, loc[1]-0))

        mix_node, mix_out = mix_float(nt, f_src, a_val, b_val, clamp=True, loc=loc)
        return mix_out

    if bl_id == "ShaderNodeAddShader":
        a_sock = socket_source(node.inputs[0])
        b_sock = socket_source(node.inputs[1])
        a_val = build_scalar_param_tree(nt, a_sock, input_name, visited, (loc[0]-140, loc[1]+60))
        b_val = build_scalar_param_tree(nt, b_sock, input_name, visited, (loc[0]-140, loc[1]-60))
        add_node, add_out = make_math(nt, 'ADD', a_val, b_val, clamp=True, loc=loc)
        return add_out

    # Groups/Volumes/other closures: conservative fallback
    v, out = make_value(nt, FALLBACK_UNSUPPORTED, (loc[0]-120, loc[1]))
    return out

def ensure_aov_output_node(nt, pass_name, loc=(1200, 0)):
    """
    Reuse or create an AOV Output and bind it to 'pass_name',
    which must match the View Layer Shader AOV entry.
    """
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeOutputAOV" and getattr(n, "aov_name", "") == pass_name:
            return n
    n = nt.nodes.new("ShaderNodeOutputAOV")
    n.aov_name = pass_name
    n.location = loc
    return n

# --- Material processing ---

def process_material(mat):
    """Compute the scalar parameter tree for INPUT_NAME and wire it to the AOV Output."""
    if not mat or not mat.use_nodes or not mat.node_tree:
        return False
    nt = mat.node_tree
    out = active_material_output(nt)
    if not out:
        return False
    surface_in = out.inputs.get('Surface', None)
    src = socket_source(surface_in)
    visited = set()
    param_socket = build_scalar_param_tree(nt, src, INPUT_NAME, visited, (800, 0))
    aov_node = ensure_aov_output_node(nt, PASS_NAME, (1100, 0))
    try:
        nt.links.new(aov_node.inputs['Value'], param_socket)  # Value pass
    except:
        nt.links.new(aov_node.inputs[1], param_socket)
    return True

def main():
    ensure_view_layer_shader_aov(bpy.context.view_layer, PASS_NAME, 'VALUE')
    count = 0
    for mat in bpy.data.materials:
        try:
            if process_material(mat):
                count += 1
        except Exception as e:
            print(f"[AOV Builder] Skipped {mat.name}: {e}")
    print(f"[AOV Builder] Updated {count} materials. Shader AOV '{PASS_NAME}' ready.")

if __name__ == "__main__":
    main()
