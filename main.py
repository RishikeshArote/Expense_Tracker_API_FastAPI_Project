from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, date
import crud, models, schemas
from database import engine, SessionLocal
from auth import get_db, login_user, get_current_user
from models import User, Budget, Expense
from typing import Optional

from sqlalchemy import func

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, db: Session = Depends(get_db), email: str = Form(...), password: str = Form(...)):
    user = login_user(request, db, email, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "msg": "Invalid credentials"})
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(request: Request, name: str = Form(...), email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return templates.TemplateResponse("register.html", {"request": request, "msg": "Email already registered"})
    
    user_data = schemas.UserCreate(name=name, email=email, password=password)
    crud.create_user(db, user_data)
    return RedirectResponse("/", status_code=302)

@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

@app.get("/add-budget", response_class=HTMLResponse)
def add_budget_form(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    # Get existing budgets to disable months that already have budgets
    existing_budgets = db.query(Budget).filter(Budget.user_id == user.id).all()
    budgeted_months = [budget.month for budget in existing_budgets]
    
    return templates.TemplateResponse("add_budget.html", {
        "request": request,
        "months": months,
        "budgeted_months": budgeted_months
    })

@app.post("/add-budget")
async def add_budget(
    request: Request,
    month: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    # Check if budget already exists for this month
    existing_budget = db.query(Budget).filter(
        Budget.user_id == user.id,
        Budget.month == month
    ).first()
    
    if existing_budget:
        raise HTTPException(status_code=400, detail="Budget already exists for this month")
    
    # Create new budget
    budget = Budget(
        user_id=user.id,
        month=month,
        year=datetime.now().year,
        amount=amount
    )
    db.add(budget)
    db.commit()
    
    return RedirectResponse("/view-budgets", status_code=303)

@app.get("/view-budgets", response_class=HTMLResponse)
def view_budgets(
    request: Request,
    month_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")

    # Initialize budget data list
    budget_data = []
    
    # Get all budgets for the user
    query = db.query(Budget).filter(Budget.user_id == user.id)
    
    if month_filter:
        query = query.filter(Budget.month == month_filter)
    
    budgets = query.order_by(Budget.month).all()
    
    # Calculate expenses for each budget
    for budget in budgets:
        # Get expenses for this month
        expenses = db.query(Expense).filter(
            Expense.user_id == user.id,
            func.extract('month', Expense.date) == datetime.strptime(budget.month, "%B").month
        ).all()
        
        # Calculate totals
        total_expenses = sum(exp.amount for exp in expenses)
        difference = budget.amount - total_expenses
        
        # Calculate expenses by category
        category_expenses = {category: 0 for category in crud.ALLOWED_CATEGORIES}
        for exp in expenses:
            category_expenses[exp.category] += exp.amount
        
        budget_data.append({
            "budget": budget,
            "total_expenses": total_expenses,
            "difference": difference,
            "category_expenses": category_expenses
        })
    
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    return templates.TemplateResponse("view_budgets.html", {
        "request": request,
        "budget_data": budget_data,
        "months": months,
        "selected_month": month_filter,
        "categories": crud.ALLOWED_CATEGORIES
    })

@app.get("/add-expense", response_class=HTMLResponse)
def add_expense_form(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    return templates.TemplateResponse("add_expense.html", {
        "request": request,
        "months": months,
        "categories": crud.ALLOWED_CATEGORIES
    })

@app.post("/add-expense")
async def add_expense(
    request: Request,
    month: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    # Validate category
    if category not in crud.ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    # Create expense
    expense = Expense(
        user_id=user.id,
        amount=amount,
        category=category,
        date=datetime.strptime(date, "%Y-%m-%d").date(),
        description=description
    )
    db.add(expense)
    db.commit()
    
    return RedirectResponse("/view-expenses", status_code=303)

@app.get("/view-expenses", response_class=HTMLResponse)
def view_expenses(
    request: Request,
    month_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    query = db.query(Expense).filter(Expense.user_id == user.id)
    
    if month_filter:
        # Use the imported func directly
        query = query.filter(func.extract('month', Expense.date) == datetime.strptime(month_filter, "%B").month)
    
    expenses = query.order_by(Expense.date.desc()).all()
    
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    return templates.TemplateResponse("view_expenses.html", {
        "request": request,
        "expenses": expenses,
        "months": months,
        "selected_month": month_filter
    })

@app.get("/edit-expense/{expense_id}", response_class=HTMLResponse)
def edit_expense_form(
    request: Request,
    expense_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == user.id
    ).first()
    
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    return templates.TemplateResponse("edit_expense.html", {
        "request": request,
        "expense": expense,
        "months": months,
        "categories": crud.ALLOWED_CATEGORIES
    })

@app.post("/update-expense/{expense_id}")
async def update_expense(
    request: Request,
    expense_id: int,
    month: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == user.id
    ).first()
    
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Validate category
    if category not in crud.ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    # Update expense
    expense.amount = amount
    expense.category = category
    expense.date = datetime.strptime(date, "%Y-%m-%d").date()
    expense.description = description
    
    db.commit()
    
    return RedirectResponse("/view-expenses", status_code=303)

@app.get("/delete-expense/{expense_id}")
def delete_expense(
    request: Request,
    expense_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == user.id
    ).first()
    
    if expense:
        db.delete(expense)
        db.commit()
    
    return RedirectResponse("/view-expenses", status_code=303)

@app.get("/summary", response_class=HTMLResponse)
def summary_page(
    request: Request,
    month: Optional[str] = None,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    # Get expenses for the selected month
    query = db.query(Expense).filter(Expense.user_id == user.id)
    
    if month:
        try:
            month_num = datetime.strptime(month, "%B").month
            query = query.filter(func.extract('month', Expense.date) == month_num)
        except ValueError:
            # Handle invalid month format
            raise HTTPException(status_code=400, detail="Invalid month format")
    
    expenses = query.all()
    
    # Calculate category totals
    category_totals = {}
    for expense in expenses:
        if expense.category not in category_totals:
            category_totals[expense.category] = 0
        category_totals[expense.category] += expense.amount
    
    # Get months for dropdown
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    return templates.TemplateResponse("summary.html", {
        "request": request,
        "category_totals": category_totals,
        "months": months,
        "selected_month": month,
        "categories": list(category_totals.keys()),
        "amounts": list(category_totals.values())
    })

@app.get("/edit-expense/{expense_id}", response_class=HTMLResponse)
def edit_expense_form(request: Request, expense_id: int, db: Session = Depends(get_db)):
    # Debugging code
    from pathlib import Path
    template_path = Path(__file__).parent / "templates" / "edit_expense.html"
    print(f"Looking for template at: {template_path}")
    print(f"Template exists: {template_path.exists()}")
    
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == user.id
    ).first()
    
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    return templates.TemplateResponse("edit_expense.html", {
        "request": request,
        "expense": expense,
        "months": months,
        "categories": crud.ALLOWED_CATEGORIES
    })



@app.post("/update-expense/{expense_id}")
async def update_expense(
    request: Request,
    expense_id: int,
    month: str = Form(...),  # Add this parameter
    amount: float = Form(...),
    category: str = Form(...),
    date: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/")
    
    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == user.id
    ).first()
    
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Validate category
    if category not in crud.ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    # Update expense
    expense.amount = amount
    expense.category = category
    expense.date = datetime.strptime(date, "%Y-%m-%d").date()
    expense.description = description
    
    db.commit()
    
    return RedirectResponse("/view-expenses", status_code=303)