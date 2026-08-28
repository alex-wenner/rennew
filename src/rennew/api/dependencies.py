from fastapi import Request

from rennew.runtime.container import RennewRuntime


def get_runtime(request: Request) -> RennewRuntime:
    runtime: RennewRuntime = request.app.state.runtime
    return runtime
