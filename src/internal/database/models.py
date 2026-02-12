from sqlmodel import SQLModel, Field


# Base model for shared configuration if needed
class BaseSQLModel(SQLModel):
    pass


# Example User model - replace with actual models from old project as needed
class User(BaseSQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    email: str = Field(index=True)


# Centralized location for all models
# Add new models here
