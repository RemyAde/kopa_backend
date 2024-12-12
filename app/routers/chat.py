from fastapi import APIRouter, Query, Depends, HTTPException, status
from app.db import get_db
from pydantic import BaseModel
from typing import List
from bson import ObjectId
from app.utils import get_current_user

router = APIRouter()


class ChatRoomCreate(BaseModel):
    name: str
    members: List[str] = []


class MemberAddRequest(BaseModel):
    username: str


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


@router.get("/my-chatrooms")
async def list_user_chatrooms(db=Depends(get_db), current_user=Depends(get_current_user)):
    # Fetch chatrooms where the current user is a member
    chatrooms = await db['chatrooms'].find({"members": current_user["username"]}).to_list(length=100)

    if not chatrooms:
        raise HTTPException(status_code=404, detail="No chatrooms found for the current user.")

    # Format the response to include necessary details
    chatroom_list = [{"id": str(chatroom["_id"]), "name": chatroom["name"], "members": chatroom["members"]} for chatroom in chatrooms]

    return {"chatrooms": chatroom_list}


@router.post("/create-chatroom")
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

    return {
        "message": f"{chatroom.name} successfully created",
        "chatroom_id": str(result.inserted_id)
        }


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
async def join_platoon_chat(
    state_code: str = Query(..., regex=r"^[A-Z]{2}/\d{2}[A-Z]/\d{4}$"), 
    db=Depends(get_db), 
    current_user=Depends(get_current_user)
    ):
    
    if len(state_code) < 1 or not state_code[-1].isdigit():
        raise HTTPException(status_code=400, detail="Invalid state code format.")
    
    existing_user = await db.users.find_one({"username": current_user["username"]})
    
    if existing_user and existing_user.get("state_code"):  # Check for a non-empty state_code value
        if existing_user["state_code"] != state_code:
            raise HTTPException(status_code=400, detail="State code conflict: This user already has a different state code.")
    
    platoon_number = int(state_code[-1]) 
    
    if platoon_number < 1 or platoon_number > 10:
        raise HTTPException(status_code=400, detail="Platoon number must be between 1 and 10.")
    
    platoon_name = f"platoon {platoon_number}"
    
    # Find the chatroom that matches the platoon name (case-insensitive)
    chatroom = await db['chatrooms'].find_one({"name": {"$regex": f"^{platoon_name}$", "$options": "i"}})
    
    if not chatroom:
        raise HTTPException(status_code=404, detail=f"{platoon_name} chat not found.")
    
    if current_user["username"] in chatroom['members']:
        raise HTTPException(status_code=400, detail="You are already a member of this chat.")
    
    await db['chatrooms'].update_one({"_id": chatroom["_id"]}, {"$push": {"members": current_user["username"]}})
    
    await db.users.update_one({"username": current_user["username"]}, {"$set": {"state_code": state_code}})
    
    updated_chatroom = await db['chatrooms'].find_one({"_id": chatroom["_id"]})
    
    return {
        "message": "Joined platoon chat successfully",
        "chatroom_id": str(updated_chatroom["_id"]),
        "members": updated_chatroom["members"]
    }