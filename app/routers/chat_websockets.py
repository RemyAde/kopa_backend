from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, HTTPException, status
from app.db import get_db
from app.models.chat import Message
from bson import ObjectId
from typing import List
from app.utils import get_current_user_from_token

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, token: str = Query(...)):

        # Get database connection
    db = await get_db()
    
    try:
        current_user = await get_current_user_from_token(token, db)
        username = current_user["username"]
    except HTTPException as e:
        print(f"Authentication failed: {e.detail}")  # Log authentication failure
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    chatroom = await db['chatrooms'].find_one({"_id": ObjectId(room_id)})
    
    if not chatroom or username not in chatroom["members"]:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    await manager.connect(websocket)  # Connect the user
    
    # Send existing messages to the newly connected user
    existing_messages = chatroom.get('messages', [])
    for msg in existing_messages:
        await websocket.send_text(f"{msg['sender']}: {msg['content']}")

    try:
        while True:
            data = await websocket.receive_text()
            message = Message(sender=username, content=data)
            await manager.send_message(data)  # Broadcast the message
            
            # Store message in database
            await db['chatrooms'].update_one(
                {"_id": ObjectId(room_id)},
                {"$push": {"messages": message.model_dump()}}
            )
    except WebSocketDisconnect:
        manager.disconnect(websocket)