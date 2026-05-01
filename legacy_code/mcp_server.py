from software.mcp_cad.mcp_server import app, server


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("software.mcp_cad.mcp_server:app", host="0.0.0.0", port=8000, log_level="info")
