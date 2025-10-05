from fastapi import FastAPI
import uvicorn

app = FastAPI()
print(">>> main.py loaded successfully <<<")
@app.get("/")
def root():
    return {"status": "OK"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)