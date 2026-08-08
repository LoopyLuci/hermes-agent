"""TypeScript worker runtime bridge."""


class NodeWorkerRuntime:
    def __init__(self, runtime_dir: str | None = None) -> None:
        self.runtime_dir = runtime_dir

    def status(self) -> dict:
        return {"node": "present" if self.runtime_dir is not None else "disabled"}

    def run(self, worker_name: str, method: str, params: dict) -> dict:
        return {"worker": worker_name, "method": method, "params": params}
