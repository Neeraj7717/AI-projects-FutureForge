import json
from fastapi import FastAPI, Response
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:3000", "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
class Input(BaseModel):
    sessionId: str
    type: str
    sdp: str
 
# Data dictionary to store offer and answer information
data = {}
 
@app.get('/test')
async def test_route():
    """Endpoint for testing the server."""
    return {"status": "ok"}
 
@app.post('/offer')
async def offer(input_data: Input):
    """Endpoint to receive offer data."""
    if input_data.type == "offer":
        # Store offer data in the data dictionary
        data["offer"] = {"sessionId": input_data.sessionId, "type": input_data.type, "sdp": input_data.sdp}
        return "success"
    else:
        return Response(status_code=400)
 
@app.post('/answer')
async def answer(input_data: Input):
    """Endpoint to receive answer data."""
    if input_data.type == "answer":
        # Store answer data in the data dictionary
        data["answer"] = {"sessionId": input_data.sessionId, "type": input_data.type, "sdp": input_data.sdp}
        return Response(status_code=200)
    else:
        return Response(status_code=400)
 
@app.get('/get_offer')
async def get_offer():
    """Endpoint to retrieve offer data."""
    if "offer" in data:
        # Serialize offer data to JSON format
        j = json.dumps(data["offer"])
        # Remove offer data from the data dictionary
        del data["offer"]
        return Response(content=j, status_code=200, media_type='application/json')
    else:
        return Response(status_code=503)
 
@app.get('/get_answer')
async def get_answer():
    """Endpoint to retrieve answer data."""
    if "answer" in data:
        # Serialize answer data to JSON format
        j = json.dumps(data["answer"])
        # Remove answer data from the data dictionary
        # del data["answer"]
        return Response(content=j, status_code=200, media_type='application/json')
    else:
        return Response(status_code=503)
 
if __name__ == '__main__':
    # Run the FastAPI application
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8061)