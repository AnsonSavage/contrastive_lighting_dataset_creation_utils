"""Entry point script for Blender rendering.

This file is executed by Blender via `--python render_manager.py` and delegates to
mode-specific strategies implemented under the `rendering` package.
"""

import sys
import pathlib
import argparse

# Ensure this file's directory is on sys.path so we can import local packages when run by Blender
current_dir = pathlib.Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from rendering.render_manager import RenderManager  # noqa: E402
from rendering.strategies import get_strategy  # noqa: E402


def main() -> None:
    try:
        dashdash_index = sys.argv.index('--')
        args_after_dashdash = sys.argv[dashdash_index + 1:]
    except ValueError:
        args_after_dashdash = sys.argv[1:]  # No '--' present

    base = argparse.ArgumentParser(description="Render entrypoint (expects arguments after '--').")
    base.add_argument('--mode', type=str, choices=['image-image', 'image-image-batch', 'image-text-instruct'], default='image-text-instruct', help='Rendering mode')
    mode_args, _ = base.parse_known_args(args_after_dashdash)

    strategy = get_strategy(mode_args.mode)
    parser = argparse.ArgumentParser(description=f"Render mode: {mode_args.mode}")
    strategy.add_args(parser)
    # Allow callers to request a list of AOVs (Arbitrary Output Variables) to be ensured
    # during the render. Default includes metallic, albedo and roughness as requested.
    parser.add_argument('--aovs', nargs='+', default=['metallic', 'albedo', 'roughness'],
                        help='List of AOVs to ensure are rendered (e.g. metallic albedo roughness)')
    args_after_dashdash = [arg for arg in args_after_dashdash if not arg.startswith('--mode=')]
    args = parser.parse_args(args_after_dashdash)

    render_manager = RenderManager()
    render_manager.set_render_settings(resolution=(512, 512), samples=32, bypass_compositing_nodes=True)
    strategy.run(args, render_manager)


if __name__ == "__main__":
    main()
