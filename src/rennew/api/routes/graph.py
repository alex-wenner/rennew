from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from rennew.api.dependencies import get_runtime
from rennew.graph.contracts import GraphQueryResult, GraphSnapshot
from rennew.graph.ladybug import UnsafeGraphQueryError
from rennew.runtime.container import RennewRuntime

router = APIRouter(prefix="/graph", tags=["graph"])
RuntimeDependency = Annotated[RennewRuntime, Depends(get_runtime)]


class GraphQuery(BaseModel):
    cypher: str = Field(min_length=1, max_length=100_000)


@router.get("/snapshot")
def graph_snapshot(runtime: RuntimeDependency) -> GraphSnapshot:
    return runtime.graph.snapshot()


@router.post("/query")
def query_graph(command: GraphQuery, runtime: RuntimeDependency) -> GraphQueryResult:
    try:
        return runtime.graph.query_readonly(command.cypher)
    except UnsafeGraphQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
