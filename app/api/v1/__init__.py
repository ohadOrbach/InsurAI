"""
API v1 Router - Aggregates all v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1 import auth, policies, coverage, search, chat, agents

router = APIRouter(tags=["v1"])

# Include sub-routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(policies.router, prefix="/policies", tags=["Policies"])
router.include_router(coverage.router, prefix="/coverage", tags=["Coverage"])
router.include_router(search.router, prefix="/search", tags=["Semantic Search"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(agents.router, tags=["Agents"])
