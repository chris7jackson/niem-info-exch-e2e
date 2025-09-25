#!/usr/bin/env python3

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


# Pydantic Models


class NiemNdrViolation(BaseModel):
    type: str  # 'error', 'warning', 'info'
    rule: str
    message: str
    location: str
    test: Optional[str] = None


class NiemNdrReport(BaseModel):
    status: str  # 'pass', 'fail', 'error'
    message: str
    conformance_target: str
    violations: List[NiemNdrViolation] = []
    summary: Dict[str, int] = {}


class SchemaResponse(BaseModel):
    schema_id: str
    niem_ndr_report: Optional[NiemNdrReport] = None
    is_active: bool


class ResetRequest(BaseModel):
    minio: bool = False
    neo4j: bool = False
    schema: bool = False
    dry_run: bool = True
    confirm_token: Optional[str] = None


class ResetResponse(BaseModel):
    counts: Dict[str, int]
    confirm_token: Optional[str] = None
    message: str