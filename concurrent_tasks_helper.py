from __future__ import annotations
import hashlib
import fcntl
from contextlib import contextmanager
import os
import csv

@contextmanager
def locked_open(path, mode):
    """Open a file and hold an exclusive lock for the duration of the context.

    Safe for concurrent writers across Slurm array tasks on Linux. On NFS, ensure
    your cluster supports fcntl-based locking (typical on modern setups).
    """
    # Ensure parent directory exists
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    f = open(path, mode)
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield f
    finally:
        try:
            f.flush()
            os.fsync(f.fileno())
        except Exception:
            pass
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()

def append_line_locked(path, line):
    with locked_open(path, "a") as f:
        f.write(line + "\n")

def write_csv_row_locked(csv_path, row):
    with locked_open(csv_path, "a",) as f:
        writer = csv.writer(f)
        writer.writerow(row)

def get_slurm_shard_from_env():
    """Infer shard (index,count) from Slurm array environment variables.

    Returns (index, count) as zero-based index and positive count. If no array is
    active, returns (0,1).
    """
    task_id = os.getenv("SLURM_ARRAY_TASK_ID")
    if not task_id:
        return 0, 1
    try:
        tid = int(task_id)
    except ValueError:
        return 0, 1
    # Derive min/max/step if available
    try:
        amin = int(os.getenv("SLURM_ARRAY_TASK_MIN", "0"))
        amax_env = os.getenv("SLURM_ARRAY_TASK_MAX")
        if amax_env is None:
            # Fallback: treat as single task if bounds are unknown
            return 0, 1
        amax = int(amax_env)
        step = int(os.getenv("SLURM_ARRAY_TASK_STEP", "1"))
        count = (amax - amin) // step + 1
        index = (tid - amin) // step
        if index < 0 or index >= count:
            # Out of bounds; fallback to single shard
            return 0, 1
        return index, count
    except Exception:
        return 0, 1

def choose_shard(args):
    # CLI overrides env
    if args.shard_count and args.shard_count > 1:
        if args.shard_index is None:
            raise ValueError("--shard-index is required when --shard-count > 1")
        if not (0 <= args.shard_index < args.shard_count):
            raise ValueError("--shard-index must satisfy 0 <= index < shard_count")
        return args.shard_index, args.shard_count
    # Else, use Slurm env if present
    return get_slurm_shard_from_env()

class ConcurrentTasksHelper():
    def __init__(self, my_worker_id: int, total_workers: int, list_of_all_tasks: list, already_completed_tasks: set):
        self.my_worker_id = my_worker_id
        self.total_workers = total_workers
        self.list_of_all_tasks = list_of_all_tasks
        self.completed_tasks = already_completed_tasks
        self.i = 0

    def in_shard(self, task_id: str, shard_idx: int, shard_cnt: int) -> bool:
        if shard_cnt <= 1:
            return True
        # Deterministic, process-stable hash
        h = int(hashlib.sha256(task_id.encode("utf-8")).hexdigest(), 16)
        return (h % shard_cnt) == shard_idx

    def get_next_task(self) -> str | None:
        while self.i < len(self.list_of_all_tasks):
            task = self.list_of_all_tasks[self.i]
            self.i += 1
            if task in self.completed_tasks:
                continue
            if self.in_shard(task, self.my_worker_id, self.total_workers):
                return task
        return None