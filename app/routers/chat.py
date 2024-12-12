from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from app.db import get_db
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from app.models.chat import Message
from app.utils import get_current_user, get_current_user_from_token, oauth2_bearer

router = APIRouter()


class ChatRoomCreate(BaseModel):
    name: str
    members: List[str] = []


@router.get("/", response_model=List[dict])
async def list_chatrooms(db=Depends(get_db), current_user=Depends(get_current_user)):
    """
    List all created chatrooms with their id, name, members, and created_at.
    """
    chatrooms = await db['chatrooms'].find().to_list(length=100)  # Modify `length` as needed
    
    # Format chatrooms for the response
    response = []
    for chatroom in chatrooms:
        response.append({
            "id": str(chatroom["_id"]),
            "name": chatroom["name"],
            "members": chatroom.get("members", [])
        })
    
    return response


@router.get("/my-chatrooms", response_model=List[dict])
async def list_user_chatrooms(db=Depends(get_db), current_user=Depends(get_current_user)):
    # Fetch chatrooms where the current user is a member
    chatrooms = await db['chatrooms'].find({"members": current_user["username"]}).to_list(length=100)

    if not chatrooms:
        raise HTTPException(status_code=404, detail="No chatrooms found for the current user.")

    # Format the response to include necessary details
    chatroom_list = [{"id": str(chatroom["_id"]), "name": chatroom["name"], "members": chatroom["members"]} for chatroom in chatrooms]

    return {"chatrooms": chatroom_list}


@router.post("/create")
async def create_chatroom(chatroom: ChatRoomCreate, db=Depends(get_db), current_user=Depends(get_current_user)):
    existing_room = await db['chatrooms'].find_one({"name": chatroom.name})
    if existing_room:
        raise HTTPException(status_code=400, detail="Chatroom already exists.")
    
    new_chatroom = {
        "name": chatroom.name,
        "members": chatroom.members,
        "messages": []
    }
    result = await db['chatrooms'].insert_one(new_chatroom)
    return {"chatroom_id": str(result.inserted_id)}


class MemberAddRequest(BaseModel):
    username: str

@router.post("/{room_id}/add-member")
async def add_member_to_chatroom(room_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    chatroom = await db['chatrooms'].find_one({"_id": ObjectId(room_id)})
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chatroom not found.")

    if current_user["username"] not in chatroom['members']:
        await db['chatrooms'].update_one({"_id": ObjectId(room_id)}, {"$push": {"members": current_user["username"]}})
    
    updated_chatroom = await db['chatrooms'].find_one({"_id": ObjectId(room_id)})
    
    return {"message": "Member added successfully", "members": updated_chatroom["members"]}


@router.post("/join-platoon-chat")
async def join_platoon_chat(state_code: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    # Validate state_code format
    if len(state_code) < 1 or not state_code[-1].isdigit():
        raise HTTPException(status_code=400, detail="Invalid state code format.")
    
    # Extract last digit as platoon number
    platoon_number = int(state_code[-1])  # Get last character and convert to int
    
    # Check if platoon_number is valid (1-10)
    if platoon_number < 1 or platoon_number > 10:
        raise HTTPException(status_code=400, detail="Platoon number must be between 1 and 10.")
    
    # Construct the expected platoon name
    platoon_name = f"platoon {platoon_number}"
    
    # Find chatroom that matches the platoon name
    chatroom = await db['chatrooms'].find_one({"name": platoon_name})
    
    if not chatroom:
        raise HTTPException(status_code=404, detail=f"{platoon_name} chat not found.")
    
    # Check if user is already a member of the chatroom
    if current_user["username"] in chatroom['members']:
        raise HTTPException(status_code=400, detail="You are already a member of this chat.")
    
    # Add user to members if they are not already in the chat
    await db['chatrooms'].update_one({"_id": chatroom["_id"]}, {"$push": {"members": current_user["username"]}})
    
    updated_chatroom = await db['chatrooms'].find_one({"_id": chatroom["_id"]})
    
    return {"message": "Joined platoon chat successfully", "members": updated_chatroom["members"]}


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


@router.websocket("/ws/{room_id}")
async def auth_headers_websocket_endpoint(websocket: WebSocket, room_id: str):
    
    # Retrieve the token from the Authorization header
    token: str = websocket.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    token = token.split(" ")[1]  # Extract the actual token
    
    # Get database connection
    db = await get_db()
    
    try:
        current_user = await get_current_user_from_token(token, db)
        username = current_user["username"]
    except HTTPException:
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
