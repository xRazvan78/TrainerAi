from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(title="trainerAI backend")


app = create_app()
