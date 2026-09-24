"""Observed population by the three official age groups."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.demographics import age_structure as build_age_structure

router = APIRouter(prefix="/demographics", tags=["demographics"])


@router.get("/structure")
async def age_structure(db: AsyncSession = Depends(get_db)):
    return await build_age_structure(db)
