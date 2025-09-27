#!/usr/bin/env python3
"""
Development server runner
"""

import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True if os.environ.get("ENVIRONMENT") == "development" else False,
        log_level="info",
        access_log=True,
    )