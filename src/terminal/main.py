import typer
from fastapi import FastAPI
import uvicorn

app = FastAPI()
cli = typer.Typer()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@cli.command()
def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the FastAPI server."""
    uvicorn.run(app, host=host, port=port)


@cli.command()
def hello(name: str):
    """Say hello to NAME."""
    print(f"Hello {name}")


if __name__ == "__main__":
    cli()
