import os
import sys
import random
from datetime import date, timedelta

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from faker import Faker
from sqlalchemy.orm import Session
from app.db.session import BusinessAdminSessionLocal, business_admin_engine
from app.db.base import BusinessBase
from app.models.business import Department, Employee, Customer, Product, Order, Sale

fake = Faker()
Faker.seed(42)
random.seed(42)


def seed_business_database():
    """
    Seeds the sample enterprise business database with coherent relational data (Task T-02).
    Ensures all 6 tables have >= 100 coherent rows (except departments which has realistic 10 core units).
    """
    print("--- [T-02] Starting Business Database Seeding ---")
    
    # Create business tables if not already created
    BusinessBase.metadata.create_all(bind=business_admin_engine)
    db: Session = BusinessAdminSessionLocal()

    try:
        # 1. Departments (10 departments)
        dept_names = [
            "Engineering", "Sales", "Marketing", "Human Resources",
            "Finance", "Operations", "Legal", "Product Management",
            "Customer Support", "Information Technology"
        ]
        departments = []
        for name in dept_names:
            dept = Department(department_name=name)
            db.add(dept)
            departments.append(dept)
        db.flush()
        print(f"[OK] Seeded {len(departments)} departments.")

        # 2. Employees (120 employees, >= 100)
        employees = []
        start_hire_date = date(2018, 1, 1)
        for _ in range(120):
            emp = Employee(
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                department_id=random.choice(departments).department_id,
                salary=round(random.uniform(45000.0, 185000.0), 2),
                hire_date=start_hire_date + timedelta(days=random.randint(0, 2200))
            )
            db.add(emp)
            employees.append(emp)
        db.flush()
        print(f"[OK] Seeded {len(employees)} employees.")

        # 3. Customers (150 customers, >= 100)
        cities = ["New York", "San Francisco", "London", "Berlin", "Tokyo", "Singapore", "Toronto", "Sydney", "Mumbai", "Paris", "Austin", "Seattle"]
        customers = []
        for _ in range(150):
            cust = Customer(
                customer_name=fake.company() if random.random() > 0.4 else fake.name(),
                city=random.choice(cities),
                total_spent=0.0
            )
            db.add(cust)
            customers.append(cust)
        db.flush()
        print(f"[OK] Seeded {len(customers)} customers.")

        # 4. Products (100 products, >= 100)
        categories = ["Electronics", "Enterprise Software", "Cloud Services", "Office Hardware", "Furniture", "Networking"]
        products = []
        for i in range(100):
            cat = random.choice(categories)
            base_price = {
                "Electronics": random.uniform(150.0, 2500.0),
                "Enterprise Software": random.uniform(500.0, 12000.0),
                "Cloud Services": random.uniform(200.0, 8000.0),
                "Office Hardware": random.uniform(80.0, 1500.0),
                "Furniture": random.uniform(120.0, 950.0),
                "Networking": random.uniform(300.0, 4500.0)
            }[cat]
            prod = Product(
                product_name=f"{cat} Item {i+1} - {fake.word().capitalize()}",
                category=cat,
                price=round(base_price, 2)
            )
            db.add(prod)
            products.append(prod)
        db.flush()
        print(f"[OK] Seeded {len(products)} products.")

        # 5. Orders (200 orders, >= 100)
        start_order_date = date(2023, 1, 1)
        orders = []
        for _ in range(200):
            order = Order(
                customer_id=random.choice(customers).customer_id,
                order_date=start_order_date + timedelta(days=random.randint(0, 450)),
                total_amount=0.0
            )
            db.add(order)
            orders.append(order)
        db.flush()
        print(f"[OK] Seeded {len(orders)} orders.")

        # 6. Sales (350 sales line items, >= 100)
        sales_count = 0
        customer_totals = {c.customer_id: 0.0 for c in customers}
        order_totals = {o.order_id: 0.0 for o in orders}

        for _ in range(350):
            order = random.choice(orders)
            product = random.choice(products)
            quantity = random.randint(1, 15)
            revenue = round(float(product.price) * quantity, 2)

            sale = Sale(
                order_id=order.order_id,
                product_id=product.product_id,
                quantity=quantity,
                revenue=revenue
            )
            db.add(sale)
            order_totals[order.order_id] += revenue
            customer_totals[order.customer_id] += revenue
            sales_count += 1

        db.flush()

        # Update order totals and customer totals to maintain relational integrity
        for order in orders:
            order.total_amount = round(order_totals[order.order_id], 2)
        for cust in customers:
            cust.total_spent = round(customer_totals[cust.customer_id], 2)

        db.commit()
        print(f"[OK] Seeded {sales_count} sales transactions.")
        print(f"[OK] Updated order totals and customer spending coherently.")
        print("--- [T-02] Business Database Seeding Completed Successfully ---")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_business_database()
