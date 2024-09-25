from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form
from bson import ObjectId
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from app.db import get_db
from app.models.news_feed import Blog
from app.models.comment import Comment, CommentCreate
from app.schemas import BlogPostCreation, BlogPostUpdate, single_blog_serializer
from app.utils import (get_current_user, fetch_user_details, create_upload_directory, 
                       validate_file_extension, save_file, create_media_file,
                       blog_creation_form)
import os
import secrets

UTC = timezone.utc

router = APIRouter()


@router.get("/feeds")
async def show_newsfeed(page: int = 1, page_size: int = 10, db = Depends(get_db), current_user = Depends(get_current_user)):
    # Validate page parameter
    if page < 1:
        page = 1

    # Calculate how many documents to skip
    skip = (page - 1) * page_size
    
    # Retrieve the posts with pagination
    blogs = await db.blogs.find().sort("created_at", -1).skip(skip).limit(page_size).to_list(length=page_size)

    data = []
    for blog in blogs:
        user = await db.users.find_one({"_id": ObjectId(blog["author"])})
        data.append({
            # use single_blog serializer to render so id can be included also
            "title": blog["title"],
            "content": blog["content"],
            "full_name": user["full_name"],
            "state_code": user["state_code"],
            "created_at": blog["created_at"]
        })
    return {"data": data, "page": page, "page_size": page_size}


@router.post("/post/create")
async def create_blog_post(
    blog_form: BlogPostCreation = Depends(blog_creation_form),
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    media_token_name = None
    file_path = None

    create_data = blog_form.model_dump(exclude_unset=True)

    try:
        if blog_form.media:
            media_token_name, file_path = await create_media_file(type="blogs", file=blog_form.media)

        blog = Blog(
            title = create_data["title"],
            content = create_data["content"],
            author = current_user.get("id"),
            media = media_token_name
        )

        await db.blogs.insert_one(blog.model_dump())

        return {"message": "Blog posted successfully!", "media_url": file_path}
    
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}


@router.get("/post/{post_id}")
async def get_post(post_id:str, db = Depends(get_db), current_user = Depends(get_current_user)):
    # retrieve single post
    # use response model
    blog = await db.blogs.find_one({"_id": ObjectId(post_id)})

    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    user = await db.users.find_one({"_id": ObjectId(blog["author"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    data = single_blog_serializer(blog, user)
    return {"data": data}


@router.put("/post/{post_id}/edit")
async def edit_post(post_id: str, blog_form: BlogPostUpdate, db = Depends(get_db), current_user = Depends(get_current_user)):
    blog = await db.blogs.find_one({"_id": ObjectId(post_id)})

    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    user = await db.users.find_one({"_id": ObjectId(blog["author"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if str(user["_id"]) != current_user.get("id"):
        raise HTTPException(status_code=401, detail="You are not authorized to edit this post")
    
    update_data = {k: v for k, v in blog_form.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided to update")

    data = await db.blogs.update_one({"_id": blog["_id"]}, {"$set": update_data})
    if data.matched_count == 0:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    return {"message": "Blog post updated successfully"}


@router.delete("/post/{post_id}/delete")
async def delete_post(post_id:str, db = Depends(get_db), current_user = Depends(get_current_user)):
    blog = await db.blogs.find_one({"_id": ObjectId(post_id)})

    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    user = await db.users.find_one({"_id": ObjectId(blog["author"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if str(user["_id"]) != current_user.get("id"):
        raise HTTPException(status_code=401, detail="You are not authorized to edit this post")
    
    await db.blogs.delete_one({"_id": blog["_id"]})

    return {"message": "blog post deleted successfully"}


@router.patch("/post/{post_id}/like")
async def like_post(post_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    # Find the blog post
    blog = await db.blogs.find_one({"_id": ObjectId(post_id)})
    
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Check if the author is the current user
    if blog["author"] == current_user.get("id"):
        raise HTTPException(status_code=400, detail="You cannot like your own post")

    # Check if the current user has already liked the post
    if "liked_by" not in blog:
        blog["liked_by"] = []  # Ensure the field exists

    if current_user["id"] in blog["liked_by"]:
        # If the user has already liked the post, we will unlike it
        await db['blogs'].update_one(
            {"_id": ObjectId(post_id)},
            {"$pull": {"liked_by": current_user["id"]}, "$inc": {"likes": -1}}
        )
        return {"message": "Post unliked"}
    
    else:
        # If the user hasn't liked the post yet, like it
        await db['blogs'].update_one(
            {"_id": ObjectId(post_id)},
            {"$push": {"liked_by": current_user["id"]}, "$inc": {"likes": 1}}
        )
        return {"message": "Post liked"}


@router.post("/post/{post_id}/comment")
async def comment_on_post(post_id:str, comment: CommentCreate, db=Depends(get_db), current_user = Depends(get_current_user)):
    
    blog = await db.blogs.find_one({"_id": ObjectId(post_id)})
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    user_id = current_user.get("id")

    new_comment = {
        "content": comment.content,
        "user_id": user_id,
        "created_at": datetime.now(UTC)
    }

    await db.blogs.update_one(
        {"_id": ObjectId(post_id)},
        {"$push": {"comments": new_comment}}
    )

    return {"message": "Comment added successfully", "comment": new_comment}


@router.get("/post/{post_id}/comments")
async def list_post_comments(post_id: str, db = Depends(get_db), current_user = Depends(get_current_user)):
    try:
        pipeline = [
            {"$match": {"_id": ObjectId(post_id)}},  # Match the blog post by post_id
            {
                "$unwind": {
                    "path": "$comments",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$addFields": {
                    "comments.user_id": {
                        "$convert": {
                            "input": "$comments.user_id",
                            "to": "objectId",
                            "onError": None,  # Handle invalid user_id format
                            "onNull": None
                        }
                    }
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "comments.user_id",
                    "foreignField": "_id",
                    "as": "comment_user"
                }
            },
            {
                "$addFields": {
                    "comments.user": {
                        "$arrayElemAt": ["$comment_user", 0]  # Extract the first user (should be only one match)
                    }
                }
            },
            {
                "$group": {
                    "_id": "$_id",
                    "title": {"$first": "$title"},
                    "content": {"$first": "$content"},
                    "author": {"$first": "$author"},
                    "likes": {"$first": "$likes"},
                    "comments": {
                        "$push": {
                            "content": "$comments.content",
                            "created_at": "$comments.created_at",
                            "user": {
                                "_id": {"$toString": "$comments.user._id"},
                                "full_name": "$comments.user.full_name"
                            }
                        }
                    },
                    "created_at": {"$first": "$created_at"},
                    "updated_at": {"$first": "$updated_at"}
                }
            }
        ]

        result = await db.blogs.aggregate(pipeline).to_list(length=1)

        # Convert ObjectIds to strings
        if result:
            result[0]["_id"] = str(result[0]["_id"])
            result[0]["author"] = str(result[0]["author"])
        
        data = jsonable_encoder(result[0]) if result else {"message": "Post not found"}

        post_fields = ["_id", "title", "content", "author", "likes", "created_at", "updated_at"]
        post_data = {key: data[key] for key in post_fields}

        post_author = await db.users.find_one({"_id": ObjectId(post_data["author"])})
        author_data = {"author_name": post_author["full_name"], "author_state_code": post_author["state_code"]}
        for k,v in author_data.items():
            post_data[k] = v
        
        comment_data = data["comments"]
        for comment in comment_data:
            user_id = comment["user"]["_id"]
            user_details = await fetch_user_details(user_id, db)  # Fetch full_name and state_code from MongoDB
            comment["user"] = user_details

        return {"post_data": post_data, "comment_data": comment_data}
        
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.put("/post/{post_id}/upload-file")
async def edit_media_file(post_id: str, file: UploadFile = File(...),
                            db = Depends(get_db), current_user = Depends(get_current_user)):
    blog = await db.blogs.find_one({"_id": ObjectId(post_id)})
    if not blog:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    # Check if the author is the current user
    if blog["author"] != current_user.get("id"):
        raise HTTPException(status_code=401, detail="You are not authorized to make changes to this post")

    filename = file.filename
    validate_file_extension(type="blogs", filename=filename)
    create_upload_directory(type="blogs")
    extension = os.path.splitext(filename)[-1].lower().replace(".", "")
    token_name = secrets.token_hex(10) +"."+ extension
    file_path = await save_file(file=file, type="blogs", filename=token_name)
    data = await db.blogs.update_one({"_id": ObjectId(post_id)}, {"$set": {"media": token_name}})
    if data.matched_count == 0:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    return JSONResponse(content={"message": "Media file uploaded successfully successfully", "file_path": file_path})