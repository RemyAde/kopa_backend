from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from app.db import get_db
from app.utils import get_current_user
from app.schemas import UserRegistrationForm

router = APIRouter()


@router.put("/registration")
async def update_user_info(user_form: UserRegistrationForm, user = Depends(get_current_user), db = Depends(get_db)):
    if user is None:
        raise HTTPException(status_code=401, detail="Authorization failed.")
    
    user_id = user.get("id")

    update_data = {k: v for k, v in user_form.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided to update")
    
    user_id = ObjectId(user_id)

    result = await db.users.update_one({"_id": user_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User updated successfully"}


@router.get("/me", status_code=status.HTTP_200_OK)
async def read_user_details(user = Depends(get_current_user)):
    if user is None:
        print("user dependency returned None")
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    return {"data": user}