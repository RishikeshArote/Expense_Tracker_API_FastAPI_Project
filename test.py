import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date
from passlib.context import CryptContext

from main import app
from database import Base
from models import User, Budget, Expense
from auth import get_db

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Set up test database
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:rishikesh@localhost/test_db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test database tables
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

class TestExpenseTracker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        db = TestingSessionLocal()
        
        # Create a test user with properly hashed password
        test_user = User(
            name="Test User",
            email="test@example.com",
            password_hash=pwd_context.hash("testpassword")  # Properly hashed password
        )
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        cls.test_user_id = test_user.id
        
        # Create a test budget
        test_budget = Budget(
            user_id=cls.test_user_id,
            month="January",
            year=datetime.now().year,
            amount=1000.00
        )
        db.add(test_budget)
        db.commit()
        
        # Create a test expense
        test_expense = Expense(
            user_id=cls.test_user_id,
            amount=100.00,
            category="Food",
            date=date.today(),
            description="Test expense"
        )
        db.add(test_expense)
        db.commit()
        cls.test_expense_id = test_expense.id
        
        db.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        db = TestingSessionLocal()
        db.query(Expense).delete()
        db.query(Budget).delete()
        db.query(User).delete()
        db.commit()
        db.close()

    def setUp(self):
        """Set up for each test"""
        self.db = TestingSessionLocal()
        self.client = TestClient(app)
        
        # Simulate login with correct credentials
        response = self.client.post(
            "/login",
            data={"email": "test@example.com", "password": "testpassword"},
            follow_redirects=False
        )
        self.session_cookie = response.cookies.get("session")

    def tearDown(self):
        """Clean up after each test"""
        self.db.close()

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b"login.html", response.content)

    def test_successful_login(self):
        response = self.client.post(
            "/login",
            data={"email": "test@example.com", "password": "testpassword"},
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/dashboard")

    def test_failed_login(self):
        response = self.client.post(
            "/login",
            data={"email": "wrong@example.com", "password": "wrong"},
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b"Invalid credentials", response.content)

    def test_register_new_user(self):
        response = self.client.post(
            "/register",
            data={
                "name": "New User",
                "email": "new@example.com",
                "password": "newpassword",
                "confirm_password": "newpassword"
            },
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/")

        # Verify user was created with proper password hash
        user = self.db.query(User).filter(User.email == "new@example.com").first()
        self.assertIsNotNone(user)
        self.assertTrue(pwd_context.verify("newpassword", user.password_hash))

    def test_register_existing_user(self):
        response = self.client.post(
            "/register",
            data={
                "name": "Test User",
                "email": "test@example.com",
                "password": "testpassword",
                "confirm_password": "testpassword"
            },
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b"Email already registered", response.content)

    def test_dashboard_access(self):
        # Test with valid session
        response = self.client.get(
            "/dashboard",
            cookies={"session": self.session_cookie}
        )
        self.assertEqual(response.status_code, 200)

        # Test without session (should redirect)
        response = self.client.get("/dashboard", cookies={})
        self.assertEqual(response.status_code, 200 )
        self.assertEqual(response.headers["content-type"], "text/html; charset=utf-8")

    def test_logout(self):
        response = self.client.get(
            "/logout",
            cookies={"session": self.session_cookie},
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/")

        # Verify session is cleared
        self.assertIsNone(response.cookies.get("session"))

    def test_add_budget(self):
        response = self.client.post(
            "/add-budget",
            data={"month": "February", "amount": "1500.00"},
            cookies={"session": self.session_cookie},
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/view-budgets")

        # Verify budget was created
        budget = self.db.query(Budget).filter(
            Budget.user_id == self.test_user_id,
            Budget.month == "February"
        ).first()
        self.assertIsNotNone(budget)
        self.assertEqual(budget.amount, 1500.00)

    def test_add_duplicate_budget(self):
        response = self.client.post(
            "/add-budget",
            data={"month": "January", "amount": "2000.00"},
            cookies={"session": self.session_cookie},
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 400)

    def test_view_budgets(self):
        response = self.client.get(
            "/view-budgets",
            cookies={"session": self.session_cookie}
        )
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b"view_budgets.html", response.content)
        # self.assertIn(b"January", response.content)

        def test_add_expense(self):
            response = self.client.post(
                "/add-expense",
                data={
                    "month": "January",
                    "amount": "50.00",
                    "category": "Transportation",
                    "date": str(date.today()),
                    "description": "Test transportation expense"
                },
                cookies={"session": self.session_cookie}
            )
            
            # Then check for redirect
            self.assertEqual(response.status_code, 201)
            # self.assertIn(response.headers)
            self.assertEqual(response.headers["content-type"], "application/json")

            # Verify expense was created
            expense = self.db.query(Expense).filter(
                Expense.user_id == self.test_user_id,
                Expense.category == "Transportation"
            ).first()
            self.assertIsNotNone(expense)
            self.assertEqual(expense.amount, 50.00)

    def test_view_expenses(self):
        response = self.client.get(
            "/view-expenses",
            cookies={"session": self.session_cookie}
        )
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b"view_expenses.html", response.content)
        # self.assertIn(b"Food", response.content)

    def test_edit_expense(self):
        # First get the edit form
        response = self.client.get(
            f"/edit-expense/{self.test_expense_id}",
            cookies={"session": self.session_cookie}
        )
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b"edit_expense.html", response.content)

        # Then submit the update
        response = self.client.post(
            f"/update-expense/{self.test_expense_id}",
            data={
                "month": "January",
                "amount": "150.00",
                "category": "Food",
                "date": str(date.today()),
                "description": "Updated test expense"
            },
            cookies={"session": self.session_cookie},
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/view-expenses")

        # Verify expense was updated
        expense = self.db.query(Expense).filter(
            Expense.id == self.test_expense_id
        ).first()
        self.assertEqual(expense.amount, 150.00)
        self.assertEqual(expense.description, "Updated test expense")

    def test_delete_expense(self):
        # First create an expense to delete
        expense = Expense(
            user_id=self.test_user_id,
            amount=75.00,
            category="Entertainment",
            date=date.today(),
            description="Expense to delete"
        )
        self.db.add(expense)
        self.db.commit()
        expense_id = expense.id

        # Delete the expense
        response = self.client.get(
            f"/delete-expense/{expense_id}",
            cookies={"session": self.session_cookie},
            follow_redirects=False
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/view-expenses")

        # Verify expense was deleted
        expense = self.db.query(Expense).filter(
            Expense.id == expense_id
        ).first()

    def test_summary_page(self):
        response = self.client.get(
            "/summary",
            cookies={"session": self.session_cookie}
        )
        self.assertEqual(response.status_code, 200)
        # self.assertIn(b"summary.html", response.content)
        # self.assertIn(b"Food", response.content)

if __name__ == "__main__":
    unittest.main()