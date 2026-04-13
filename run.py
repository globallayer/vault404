import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("vault404.api.server:app", host="0.0.0.0", port=port)
