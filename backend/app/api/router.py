from fastapi import APIRouter

from . import ai, analysis, auth, cases, evidence, health, relationships, reports

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(evidence.router)
api_router.include_router(analysis.router)
api_router.include_router(relationships.router)
api_router.include_router(ai.router)
api_router.include_router(reports.router)
