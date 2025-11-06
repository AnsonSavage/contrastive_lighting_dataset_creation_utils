should_log = True

def log(msg: str) -> None:
    if should_log:
        print(f"[render_manager] {msg}", flush=True)
