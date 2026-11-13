from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from rennew.agent.loop import ProviderNotConfiguredError, SessionBusyError
from rennew.api.dependencies import get_runtime
from rennew.runtime.container import RennewRuntime
from rennew.sessions.models import (
    Compaction,
    CompactionCreate,
    FileChange,
    Handoff,
    HandoffCreate,
    PromptRequest,
    Session,
    SessionCreate,
    SessionMessage,
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


@router.get("/{session_id}/messages")
def list_messages(session_id: str, runtime: RuntimeDependency) -> list[SessionMessage]:
    try:
        return runtime.sessions.list_messages(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error


@router.get("/{session_id}/changes")
def list_changes(session_id: str, runtime: RuntimeDependency) -> list[FileChange]:
    try:
        runtime.sessions.get(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error
    return runtime.graph.list_file_changes(session_id)


@router.post("/{session_id}/prompt", status_code=status.HTTP_200_OK)
async def prompt_session(
    session_id: str, request: PromptRequest, runtime: RuntimeDependency
) -> SessionMessage:
    """Run one real agent turn: stream the provider, execute tools, persist to the graph."""
    try:
        return await runtime.agent.run_turn(session_id, request)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail="Session not found.") from error
    except ProviderNotConfiguredError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except SessionBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
