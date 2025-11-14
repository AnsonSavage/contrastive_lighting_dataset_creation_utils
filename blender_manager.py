from environment import BLENDER_PATH, DATA_PATH
import threading
import subprocess
import os

class BlenderManager:
    def open_blender_file_with_args(
        self,
        *,
        file_path: str,
        python_script_path: str,
        args_for_python_script=None,
        background: bool = False,
    ) -> int:
        """Open a Blender file and run a Python script with additional args.

        All arguments are keyword-only to avoid ambiguity like "multiple values
        for argument 'file_path'" when mixing positional and keyword args.

        :param file_path: Path to the .blend file.
        :param python_script_path: Path to the Python script to run inside Blender.
        :param args_for_python_script: Extra args passed after "--" to the script.
        :param background: If True, add --background. If False, omit it.
        :return: Blender process return code.
        """
        if args_for_python_script is None:
            args_for_python_script = []

        blender_command = [BLENDER_PATH]
        if file_path:
            blender_command.append(file_path)
        if background:
            blender_command.append("--background")
        blender_command += ["--python", python_script_path, "--"]
        blender_command += list(args_for_python_script)
        os.environ.setdefault("PYTHONUNBUFFERED", "1")

        print("Running Blender command:", " ".join(blender_command), flush=True)

        proc = subprocess.Popen(
            blender_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # Line-buffered text mode
        )

        stdout_thread = threading.Thread(
            target=self.stream_output,
            args=(proc.stdout, "STDOUT")
        )
        stderr_thread = threading.Thread(
            target=self.stream_output,
            args=(proc.stderr, "STDERR")
        )

        stdout_thread.start()
        stderr_thread.start()

        return_code = proc.wait(timeout=None)  # TODO: you could add a timeout if you want
        
        stdout_thread.join()
        stderr_thread.join()

        print("Blender process completed successfully.", flush=True)
        return return_code

    def stream_output(self, pipe, prefix):
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                print(f"[{prefix}] {line.rstrip()}", flush=True)
            pipe.close()