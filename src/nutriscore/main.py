from fastapi import FastAPI

app = FastAPI(title="nutriscore")


@app.get("/hello")
def hello() -> dict[str, str]:
    return {"message": "hello world"}
