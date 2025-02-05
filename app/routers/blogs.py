from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form, Request
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

router = APIRouter()

UTC = timezone.utc


@router.get("/feeds")
async def show_newsfeed(page: int = 1, page_size: int = 10, db = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Retrieves paginated blog posts for the newsfeed.
    This asynchronous function fetches blog posts from the database with pagination support,
    including associated user information for each post.
    Args:
        page (int, optional): The page number to retrieve. Defaults to 1.
        page_size (int, optional): Number of posts per page. Defaults to 10.
        db: Database connection dependency.
        current_user: Currently authenticated user dependency.
    Returns:
        dict: A dictionary containing:
            - data (list): List of blog posts with author information
            - page (int): Current page number
            - page_size (int): Number of items per page
    Each blog post in the data list contains:
        - title (str): Title of the blog post
        - content (str): Content of the blog post
        - media (str): Media URL if available, empty string if none
        - full_name (str): Author's full name
        - state_code (str): Author's state code
        - created_at (datetime): Post creation timestamp
    """

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
        media = blog['media'] if blog["media"] else ""
        data.append({
            # use single_blog serializer to render so id can be included also
            "title": blog["title"],
            "content": blog["content"],
            "media": media,
            "full_name": user["full_name"],
            "state_code": user["state_code"],
            "created_at": blog["created_at"]
            # find a way to serialize thsi data
        })
        
    return {"data": data, "page": page, "page_size": page_size}


@router.post("/post/create")
async def create_blog_post(
    request: Request,
    blog_form: BlogPostCreation = Depends(blog_creation_form),
    db=Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Create a new blog post with optional media attachment.
    Args:
        request (Request): The FastAPI request object containing base URL info
        blog_form (BlogPostCreation): Form data for creating blog post, validated by blog_creation_form dependency
        db: Database connection from dependency injection
        current_user (dict): Currently authenticated user from dependency injection
    Returns:
        dict: Success message if blog created successfully, error message if creation fails
            Success format: {"message": "Blog posted successfully!"}
            Error format: {"error": "An error occurred: <error details>"}
    Raises:
        Exception: If any error occurs during blog creation or media upload process
    Note:
        - Media files are stored in static/uploads/blogs directory
        - Full media URL is constructed using request.base_url
    """
    media_token_name = None

    create_data = blog_form.model_dump(exclude_unset=True)

    try:
        if blog_form.media:
            media_token_name = await create_media_file(type="blogs", file=blog_form.media)

        blog = Blog(
            title = create_data["title"],
            content = create_data["content"],
            author = current_user.get("id"),
            # media = media_token_name,
            media = f"{request.base_url}static/uploads/blogs/{media_token_name}"

        )

        await db.blogs.insert_one(blog.model_dump())

        return {"message": "Blog posted successfully!"}
    
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}


@router.get("/post/{post_id}")
async def get_post(post_id:str, db = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Retrieves a single blog post by its ID along with the author information.
    Args:
        post_id (str): The ID of the blog post to retrieve
        db: Database connection dependency
        current_user: Currently authenticated user dependency
    Returns:
        dict: A dictionary containing the blog post data with author information in the format:
            {
                "data": {
                    # Serialized blog post with author details
                }
            }
    Raises:
        HTTPException: 404 error if blog post or author is not found
    Dependencies:
        - get_db: Database connection provider
        - get_current_user: Authentication dependency
    """

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
    """
    Updates an existing blog post in the database.
    Args:
        post_id (str): The ID of the blog post to edit
        blog_form (BlogPostUpdate): Pydantic model containing the updated blog post data
        db: Database dependency instance
        current_user: The currently authenticated user dependency
    Returns:
        dict: A message confirming successful update
    Raises:
        HTTPException(404): If blog post or user is not found
        HTTPException(401): If user is not authorized to edit the post
        HTTPException(400): If no update data is provided
    """

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
    """
    Deletes a blog post from the database.
    This function checks if:
    1. The blog post exists
    2. The author of the post exists
    3. The current user is the author of the post
    Args:
        post_id (str): The ID of the blog post to delete
        db: Database dependency injection
        current_user: The currently authenticated user
    Raises:
        HTTPException: 
            - 404 if blog post not found
            - 404 if user not found
            - 401 if user is not authorized to delete the post
    Returns:
        dict: A message confirming successful deletion
    """

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
    """
    Handle liking/unliking a blog post by a user.
    This function manages the like functionality for blog posts. It allows users to like 
    or unlike posts, maintaining a list of users who liked each post and a count of total likes.
    The function prevents users from liking their own posts and handles both like and unlike
    operations in a single endpoint.
    Parameters:
        post_id (str): The ID of the blog post to like/unlike
        db (Database): MongoDB database instance obtained through dependency injection
        current_user (dict): The authenticated user's information obtained through dependency injection
    Returns:
        dict: A message indicating whether the post was liked or unliked
    Raises:
        HTTPException: 
            - 404 if blog post is not found
            - 400 if user tries to like their own post
    Example:
        >>> await like_post("507f1f77bcf86cd799439011", db, current_user)
        {"message": "Post liked"}
    """

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
    """Adds a comment to a specific blog post.
    This asynchronous function creates and adds a new comment to a blog post, associating it
    with the current authenticated user.
    Args:
        post_id (str): The ID of the blog post to comment on.
        comment (CommentCreate): The comment content object.
        db: Database connection dependency.
        current_user: The authenticated user making the comment.
    Returns:
        dict: A dictionary containing a success message and the created comment data.
    Raises:
        HTTPException: If the blog post with the given ID is not found (404).
    """
    
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
    """
    Retrieve a blog post and its comments with associated user details.
    This async function performs an aggregation pipeline to fetch a blog post by its ID
    and all associated comments, including user details for both the post author and comment authors.
    Parameters:
    ----------
    post_id : str
        The ID of the blog post to retrieve
    db : AsyncIOMotorDatabase
        Database connection instance from dependency injection
    current_user : dict
        Current authenticated user details from dependency injection
    Returns:
    -------
    dict
        A dictionary containing:
            - post_data: Post details including title, content, author info, likes, timestamps
            - comment_data: List of comments with associated user details
    Raises:
    ------
    HTTPException
        400 - If there's an error processing the request (invalid ID format, database errors)
    Notes:
    -----
    The function performs the following main operations:
    1. Aggregates post data with comments using MongoDB pipeline
    2. Converts ObjectIDs to strings for JSON serialization
    3. Fetches additional author details
    4. Retrieves detailed user information for each comment
    """

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
        # add a serialization to check for and include media
        
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.put("/post/{post_id}/upload-file")
async def edit_media_file(request: Request, post_id: str, file: UploadFile = File(...),
                            db = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Edits media file for a specific blog post.
    This async function handles the upload and replacement of media files for existing blog posts.
    It validates user authorization, file type, and updates the database with the new media URL.
    Args:
        request (Request): FastAPI request object containing base URL information
        post_id (str): ID of the blog post to update
        file (UploadFile): The media file to upload
        db: Database connection dependency
        current_user: Current authenticated user dependency
    Returns:
        JSONResponse: A JSON response indicating successful media upload
    Raises:
        HTTPException: 
            - 404: If blog post is not found
            - 401: If user is not authorized to edit the post
            - 400: If file extension is invalid (through validate_file_extension)
    Example:
        >>> await edit_media_file(request, "507f1f77bcf86cd799439011", file, db, user)
        {"message": "Media file uploaded successfully successfully"}
    """
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
    await save_file(file=file, type="blogs", filename=token_name)

    media = f"{request.base_url}static/uploads/blogs/{token_name}"
    data = await db.blogs.update_one({"_id": ObjectId(post_id)}, {"$set": {"media": media}})
    if data.matched_count == 0:
        raise HTTPException(status_code=404, detail="Blog post not found")
    
    return JSONResponse(content={"message": "Media file uploaded successfully successfully"})