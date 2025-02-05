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
    """
    Retrieves a list of chatrooms where the current user is a member.
    -Args:
        -db: Database session dependency (MongoDB)
        -current_user (dict): The currently authenticated user's information
    -Returns:
        -dict: A dictionary containing list of chatrooms with their details:
            - chatrooms: List of dictionaries with following structure:
                - id (str): Chatroom's unique identifier
                - name (str): Name of the chatroom
                - members (list): List of usernames who are members of the chatroom
    -Raises:
        -HTTPException: If no chatrooms are found for the current user (404)
    """

    # Fetch chatrooms where the current user is a member
    chatrooms = await db['chatrooms'].find({"members": current_user["username"]}).to_list(length=100)

    if not chatrooms:
        raise HTTPException(status_code=404, detail="No chatrooms found for the current user.")

    # Format the response to include necessary details
    chatroom_list = [{"id": str(chatroom["_id"]), "name": chatroom["name"], "members": chatroom["members"]} for chatroom in chatrooms]

    return {"chatrooms": chatroom_list}


@router.post("/create-chatroom")
async def create_chatroom(chatroom: ChatRoomCreate, db=Depends(get_db), current_user=Depends(get_current_user)):
    """
    Create a new chatroom in the database.
    This async function creates a new chatroom with the given name and members. It first checks if a
    chatroom with the same name already exists to prevent duplicates.
    Parameters
    ----------
    -chatroom : ChatRoomCreate
        -Pydantic model containing the chatroom details (name and members)
    -db : AsyncIOMotorDatabase
        -Database connection instance obtained from dependency injection
    -current_user : dict
        -Current authenticated user details obtained from dependency injection
    Returns
    -------
    -dict
        A dictionary containing:
        - message: Success message with the chatroom name
        - chatroom_id: String representation of the created chatroom's ObjectId
    Raises
    ------
    -HTTPException
        -400 error if a chatroom with the same name already exists
    Examples
    --------
    >>> chatroom_data = ChatRoomCreate(name="New Room", members=["user1", "user2"])
    >>> result = await create_chatroom(chatroom_data, db, current_user)
    >>> print(result)
    {
        "message": "New Room successfully created",
        "chatroom_id": "507f1f77bcf86cd799439011"
    """

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
    """
    Adds the current user to a chatroom's member list if they are not already a member.
    Args:
        room_id (str): The ID of the chatroom to add the member to
        db: Database dependency injection (MongoDB instance)
        current_user: The authenticated user making the request
    Returns:
        dict: A dictionary containing:
            - message (str): Success message
            - members (list): Updated list of members in the chatroom
    Raises:
        HTTPException: 404 if chatroom is not found
    Example:
        >>> result = await add_member_to_chatroom("507f1f77bcf86cd799439011")
        >>> print(result)
        {"message": "Member added successfully", "members": ["user1", "user2"]}
    """

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
    """
    Asynchronously adds a user to a platoon chat room based on a state code.
    Parameters:
        state_code (str): A formatted string following pattern 'XX/00X/0000' where X is a letter and 0 is a digit. 
                         The last digit represents the platoon number (1-10).
        db: Database connection dependency injection.
        current_user (dict): The authenticated user information obtained via dependency injection.
    Returns:
        dict: A dictionary containing:
            - message: Success message
            - chatroom_id: The ID of the joined chatroom
            - members: List of all members in the chatroom
    Raises:
        HTTPException(400): If state code format is invalid
        HTTPException(400): If user already has a different state code
        HTTPException(400): If platoon number is not between 1 and 10
        HTTPException(400): If user is already a member of the chat
        HTTPException(404): If platoon chat room is not found
    Example:
        >>> await join_platoon_chat(state_code="NY/12A/1234", db=db, current_user=user)
        {
            "chatroom_id": "507f1f77bcf86cd799439011",
            "members": ["user1", "user2"]
    """

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