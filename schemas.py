from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date

# ------------------ User Schemas ------------------

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        orm_mode = True

# ------------------ Expense Schemas ------------------

class ExpenseCreate(BaseModel):
    date: date  # Only one field instead of year/month/day
    amount: float
    category: Literal["a1", "b2", "c3", "d4", "e5"]
    description: Optional[str] = ""

class ExpenseOut(BaseModel):
    id: int
    date: date
    amount: float
    category: str
    description: Optional[str] = ""

    class Config:
        orm_mode = True

# ------------------ Budget Schemas ------------------

class BudgetCreate(BaseModel):
    year: int = Field(..., ge=2001, le=2100)
    month: int = Field(..., ge=1, le=12)
    amount: float

    class Config:
        orm_mode = True

class BudgetOut(BudgetCreate):
    id: int

    class Config:
        orm_mode = True
