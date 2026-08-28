from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from rennew.api.dependencies import get_runtime
from rennew.runtime.container import RennewRuntime
from rennew.sessions.models import (
    Compaction,
    CompactionCreate,
    Handoff,
    HandoffCreate,
    Session,
    SessionCreate,
    SessionOverlap,
    SessionOverlapCreate,
)
from rennew.sessions.service import SessionNotFoundError

router = APIRouter(prefix="/sessions", tags=["sessions"])
RuntimeDependency = Annotated[RennewRuntime, Depends(get_runtime)]


@router.get("")
def list_sessions(runtime: RuntimeDependency) -> list[Session]:
    return runtime.sessions.list_sessions()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(command: SessionCreate, runtime: RuntimeDependency) -> Session:
    return runtime.sessions.create(command)


@router.get("/{session_id}")
def get_session(session_id: str, runtime: RuntimeDependency) -> Session:
    try:
        return runtime.sessions.get(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error


@router.post("/{session_id}/handoffs", status_code=status.HTTP_201_CREATED)
def create_handoff(
    session_id: str, command: HandoffCreate, runtime: RuntimeDependency
) -> Handoff:
    try:
        return runtime.sessions.handoff(session_id, command)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error


@router.post("/{session_id}/overlaps", status_code=status.HTTP_201_CREATED)
def create_overlap(
    session_id: str, command: SessionOverlapCreate, runtime: RuntimeDependency
) -> SessionOverlap:
    try:
        return runtime.sessions.overlap(session_id, command)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error


@router.post("/{session_id}/compactions", status_code=status.HTTP_201_CREATED)
def create_compaction(
    session_id: str, command: CompactionCreate, runtime: RuntimeDependency
) -> Compaction:
    try:
        return runtime.sessions.compact(session_id, command)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error


@router.get("/{session_id}/compactions")
def list_compactions(session_id: str, runtime: RuntimeDependency) -> list[Compaction]:
    try:
        return runtime.sessions.list_compactions(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error
