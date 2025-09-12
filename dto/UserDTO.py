


# User DTO.
# used to save data of a user. 



from typing import List
from pydantic import BaseModel, Field


class UserInfoDTO(BaseModel):
    """
    DTO for user information, composed from the "UserInfo" and "emailList" tables.
    """
    commitary_id: int = Field(..., description="Primary key of the UserInfo table.")
    github_id: int | None = Field(None, description="GitHub-defined user ID.")
    github_name: str | None = Field(None, description="Username on GitHub.")
    defaultEmail: str | None = Field(None, description="The user's default email address.")
    github_url: str | None = Field(None, description="API URL for the user's GitHub profile.")
    github_html_url: str | None = Field(None, description="Web URL for the user's GitHub profile.")
    # email_list: List[EmailDTO] = Field(..., description="A list of all emails for this user.") # leave as a blank
    
