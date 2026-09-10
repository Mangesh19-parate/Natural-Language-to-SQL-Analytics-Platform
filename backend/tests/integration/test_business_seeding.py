from scripts.seed_business_db import seed_business_database
from app.db.session import BusinessAdminSessionLocal
from app.models.business import Department, Employee, Customer, Product, Order, Sale


def test_business_seed_data_counts():
    """
    T-02 Acceptance Criteria:
    Seed script populates tables with >= 100 rows each.
    """
    # Run seeder
    seed_business_database()

    db = BusinessAdminSessionLocal()
    try:
        dept_count = db.query(Department).count()
        emp_count = db.query(Employee).count()
        cust_count = db.query(Customer).count()
        prod_count = db.query(Product).count()
        order_count = db.query(Order).count()
        sales_count = db.query(Sale).count()

        print(f"\nSeeded counts: depts={dept_count}, emps={emp_count}, custs={cust_count}, prods={prod_count}, orders={order_count}, sales={sales_count}")

        assert dept_count >= 10, f"Expected >= 10 departments, got {dept_count}"
        assert emp_count >= 100, f"Expected >= 100 employees, got {emp_count}"
        assert cust_count >= 100, f"Expected >= 100 customers, got {cust_count}"
        assert prod_count >= 100, f"Expected >= 100 products, got {prod_count}"
        assert order_count >= 100, f"Expected >= 100 orders, got {order_count}"
        assert sales_count >= 100, f"Expected >= 100 sales, got {sales_count}"

        # Verify relational data integrity
        # First order has matching customer
        sample_order = db.query(Order).first()
        assert sample_order.customer is not None
        assert sample_order.total_amount >= 0

        # Sample sale has order and product
        sample_sale = db.query(Sale).first()
        assert sample_sale.order is not None
        assert sample_sale.product is not None
        assert sample_sale.revenue > 0

    finally:
        db.close()
