"""Agent CRUD routes for customizable analysis hierarchy."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...models import User, CustomAgent
from ...models.db import get_db
from ...models.base import new_uuid
from ..auth import get_current_user
from ..schemas.agents import (
    AgentCreateRequest, AgentUpdateRequest, AgentResponse, AgentTreeResponse,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentTreeResponse)
def list_agents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all agents for the current user (flat list, build tree client-side)."""
    agents = (
        db.query(CustomAgent)
        .filter_by(user_id=user.id)
        .order_by(CustomAgent.sort_order)
        .all()
    )
    return AgentTreeResponse(agents=agents)


@router.post("", response_model=AgentResponse, status_code=201)
def create_agent(
    body: AgentCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new agent in the user's hierarchy."""
    # Validate parent belongs to same user
    if body.parent_id:
        parent = db.query(CustomAgent).filter_by(id=body.parent_id, user_id=user.id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent agent not found")

    agent = CustomAgent(
        id=new_uuid(),
        user_id=user.id,
        name=body.name,
        agent_type=body.agent_type,
        parent_id=body.parent_id,
        prompt=body.prompt,
        weight=body.weight,
        enabled=body.enabled,
        sort_order=body.sort_order,
        config=body.config,
    )
    db.add(agent)
    db.flush()
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an agent's properties."""
    agent = db.query(CustomAgent).filter_by(id=agent_id, user_id=user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Validate new parent if changing
    if body.parent_id is not None:
        if body.parent_id == agent.id:
            raise HTTPException(status_code=400, detail="Agent cannot be its own parent")
        if body.parent_id != "":
            parent = db.query(CustomAgent).filter_by(id=body.parent_id, user_id=user.id).first()
            if not parent:
                raise HTTPException(status_code=404, detail="Parent agent not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    db.flush()
    return agent


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an agent. Children are re-parented to the deleted agent's parent."""
    agent = db.query(CustomAgent).filter_by(id=agent_id, user_id=user.id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Re-parent children
    children = db.query(CustomAgent).filter_by(parent_id=agent.id, user_id=user.id).all()
    for child in children:
        child.parent_id = agent.parent_id
    db.flush()

    db.delete(agent)
    db.flush()


@router.post("/reset", response_model=AgentTreeResponse)
def reset_agents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset the user's agent hierarchy to the default configuration."""
    # Delete all existing agents
    db.query(CustomAgent).filter_by(user_id=user.id).delete()
    db.flush()

    # Re-create defaults
    from .auth import _create_default_agent_hierarchy
    _create_default_agent_hierarchy(db, user.id)

    agents = (
        db.query(CustomAgent)
        .filter_by(user_id=user.id)
        .order_by(CustomAgent.sort_order)
        .all()
    )
    return AgentTreeResponse(agents=agents)
