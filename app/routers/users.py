from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile, Request
from bson import ObjectId
from app.db import get_db
from app.utils import get_current_user, user_registration_form, create_media_file
from app.schemas import UserRegistrationForm

router = APIRouter()


@router.put("/registration")
async def update_user_info(
    request: Request, user_form: UserRegistrationForm = Depends(user_registration_form),  # Inject form data dependency
    user = Depends(get_current_user),  # Authorization
    db = Depends(get_db),  # Database
):
    if user is None:
        raise HTTPException(status_code=401, detail="Authorization failed.")
    
    user_id = user.get("id")

    update_data = user_form.model_dump(exclude_unset=True)  # Get the validated data from the Pydantic model
    
    # Check for duplicate state code
    existing_state_code = await db.users.find_one({"state_code": user_form.state_code})
    if existing_state_code:
        raise HTTPException(status_code=400, detail="User with this state code already exists.")
    
    # Optional: Handle image file processing
    if user_form.profile_image:
        image_token_name = await create_media_file(type="users", file=user_form.profile_image)
        update_data["profile_image"] = f"{request.base_url}static/uploads/users/{image_token_name}"
    
    user_id = ObjectId(user_id)

    result = await db.users.update_one({"_id": user_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User updated successfully"}


@router.put("/update-profile-image")
async def update_profile_image(request: Request, profile_image: UploadFile = File(...), current_user = Depends(get_current_user), db = Depends(get_db)):
    if not profile_image:
        raise HTTPException(status_code=400, detail="You must upload an image file")
    
    media_token_name = await create_media_file(type="users", file=profile_image)

    user_id = current_user.get("id")
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"profile_image": f"{request.base_url}static/uploads/users/{media_token_name}"}})

    return {"message": "profile image updated succcessfully"}


@router.get("/me", status_code=status.HTTP_200_OK)
async def read_user_details(user = Depends(get_current_user)):
    if user is None:
        print("user dependency returned None")
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    return {"data": user}