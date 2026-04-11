from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr


class RegisterResponse(BaseModel):
    api_key: str
    email: str
    message: str
