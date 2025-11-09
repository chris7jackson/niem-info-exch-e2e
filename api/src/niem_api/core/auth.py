#!/usr/bin/env python3

import os
import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Default token for development - CHANGE THIS IN PRODUCTION!
DEFAULT_DEV_TOKEN = "devtoken"


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify dev token"""
    expected_token = os.getenv("DEV_TOKEN", DEFAULT_DEV_TOKEN)

    # Warn if using default token
    if expected_token == DEFAULT_DEV_TOKEN:
        logger.warning("⚠️  Using default DEV_TOKEN='devtoken'. " "Set DEV_TOKEN environment variable for production!")

    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return credentials.credentials
