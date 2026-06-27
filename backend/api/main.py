import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="AI SRE Copilot API",
    description="Autonomous incident response assistant API Gateway.",
    version="0.1.0",
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify backend status."""
    return {"status": "ok", "message": "AI SRE Copilot API is healthy"}


# Mount frontend build directory (if exists)
frontend_dist_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../frontend/dist")
)
if os.path.exists(frontend_dist_path):
    app.mount(
        "/", StaticFiles(directory=frontend_dist_path, html=True), name="frontend"
    )
else:

    @app.get("/")
    async def root():
        return {"message": "FastAPI is running. Frontend build not found."}
