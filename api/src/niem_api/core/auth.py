#!/usr/bin/env python3

import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify dev token"""
    expected_token = os.getenv("DEV_TOKEN", "devtoken")

    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )

    return credentials.credentials
