from typing import Optional

from database.manager import BaseModel


class User(BaseModel):
    table_name: Optional[str] = "users"


class OAuthClient(BaseModel):
    table_name: Optional[str] = "oauth_clients"


class AuthorizationCode(BaseModel):
    table_name: Optional[str] = "oauth_authorization_codes"


class AccessToken(BaseModel):
    table_name: Optional[str] = "oauth_access_tokens"


class RegisteredDevice(BaseModel):
    table_name: Optional[str] = "registered_devices"
