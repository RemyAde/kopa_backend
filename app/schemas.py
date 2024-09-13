def single_user_serializer(user) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "verification_code": user["verification_code"],
        "is_active": user["is_active"]
    }