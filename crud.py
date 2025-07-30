from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import models, schemas
from passlib.hash import bcrypt
from datetime import datetime

# ---------------------- USER ----------------------
def create_user(db: Session, user: schemas.UserCreate):
    hashed_pw = bcrypt.hash(user.password)
    db_user = models.User(name=user.name, email=user.email, password_hash=hashed_pw)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user and bcrypt.verify(password, user.password_hash):
        return user
    return None

# ---------------------- EXPENSE ----------------------
ALLOWED_CATEGORIES = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Shopping']

def create_expense(db: Session, user_id: int, expense: schemas.ExpenseCreate):
    if expense.category not in ALLOWED_CATEGORIES:
        raise ValueError(f"Invalid category. Allowed categories: {ALLOWED_CATEGORIES}")
    db_exp = models.Expense(**expense.dict(), user_id=user_id)
    db.add(db_exp)
    db.commit()
    db.refresh(db_exp)
    return db_exp

def get_expenses(db: Session, user_id: int):
    return db.query(models.Expense)\
        .filter(models.Expense.user_id == user_id)\
        .order_by(desc(models.Expense.date))\
        .all()

def get_expenses_by_month(db: Session, user_id: int, month: str):
    """Get expenses for a specific month (by name)"""
    month_number = datetime.strptime(month, "%B").month
    return db.query(models.Expense)\
        .filter(
            models.Expense.user_id == user_id,
            func.extract('month', models.Expense.date) == month_number
        )\
        .order_by(desc(models.Expense.date))\
        .all()

def delete_expense(db: Session, expense_id: int):
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if expense:
        db.delete(expense)
        db.commit()

def update_expense(db: Session, expense_id: int, updated: schemas.ExpenseCreate):
    if updated.category not in ALLOWED_CATEGORIES:
        raise ValueError(f"Invalid category. Allowed categories: {ALLOWED_CATEGORIES}")
    expense = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if expense:
        for key, value in updated.dict().items():
            setattr(expense, key, value)
        db.commit()
        db.refresh(expense)
        return expense
    return None

# ---------------------- BUDGET ----------------------
def create_budget(db: Session, user_id: int, month: str, amount: float):
    """Create a budget for a specific month (without year tracking)"""
    budget = models.Budget(
        user_id=user_id,
        month=month,
        year=datetime.now().year,  # Store current year but don't use it for filtering
        amount=amount
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget

def get_budget(db: Session, user_id: int, month: str):
    """Get budget for a specific month (latest year if multiple exist)"""
    return db.query(models.Budget)\
        .filter(
            models.Budget.user_id == user_id,
            models.Budget.month == month
        )\
        .order_by(desc(models.Budget.year))\
        .first()

def get_all_budgets(db: Session, user_id: int):
    """Get all budgets for user (monthly, without year consideration)"""
    # Get only the latest budget for each month
    subquery = db.query(
        models.Budget.month,
        func.max(models.Budget.year).label('max_year')
        )\
        .filter(models.Budget.user_id == user_id)\
        .group_by(models.Budget.month)\
        .subquery()

    return db.query(models.Budget)\
        .join(
            subquery,
            (models.Budget.month == subquery.c.month) &
            (models.Budget.year == subquery.c.max_year)
        )\
        .filter(models.Budget.user_id == user_id)\
        .all()

def update_budget(db: Session, user_id: int, month: str, amount: float):
    """Update or create budget for a month"""
    budget = get_budget(db, user_id, month)
    if budget:
        budget.amount = amount
    else:
        budget = create_budget(db, user_id, month, amount)
    db.commit()
    return budget

# ---------------------- SUMMARY ----------------------
def get_monthly_summary(db: Session, user_id: int, month: str = None):
    """Get comprehensive monthly summary data"""
    result = {
        'total_budget': 0,
        'total_expenses': 0,
        'category_expenses': {c: 0 for c in ALLOWED_CATEGORIES},
        'difference': 0
    }

    # Get budgets (all or filtered by month)
    budgets = []
    if month:
        budget = get_budget(db, user_id, month)
        if budget:
            budgets = [budget]
    else:
        budgets = get_all_budgets(db, user_id)

    # Calculate totals
    result['total_budget'] = sum(b.amount for b in budgets)

    # Get expenses (all or filtered by month)
    expenses = []
    if month:
        expenses = get_expenses_by_month(db, user_id, month)
    else:
        expenses = get_expenses(db, user_id)

    # Calculate expense totals
    result['total_expenses'] = sum(e.amount for e in expenses)
    result['difference'] = result['total_budget'] - result['total_expenses']

    # Calculate category breakdown
    for expense in expenses:
        result['category_expenses'][expense.category] += expense.amount

    return result

def get_total_expenses(db: Session, user_id: int):
    total = db.query(func.sum(models.Expense.amount)).filter(models.Expense.user_id == user_id).scalar()
    return total or 0

def get_total_budget(db: Session, user_id: int):
    total = db.query(func.sum(models.Budget.amount)).filter(models.Budget.user_id == user_id).scalar()
    return total or 0