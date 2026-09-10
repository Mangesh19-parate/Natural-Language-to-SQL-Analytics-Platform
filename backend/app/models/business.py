from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import BusinessBase


class Department(BusinessBase):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True, index=True)
    department_name = Column(String(100), nullable=False)

    employees = relationship("Employee", back_populates="department")


class Employee(BusinessBase):
    __tablename__ = "employees"

    employee_id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.department_id"), nullable=True)
    salary = Column(Numeric(12, 2), nullable=False)
    hire_date = Column(Date, nullable=False)

    department = relationship("Department", back_populates="employees")


class Customer(BusinessBase):
    __tablename__ = "customers"

    customer_id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(150), nullable=False)
    city = Column(String(100), nullable=False)
    total_spent = Column(Numeric(12, 2), default=0)

    orders = relationship("Order", back_populates="customer")


class Product(BusinessBase):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(150), nullable=False)
    category = Column(String(100), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)

    sales = relationship("Sale", back_populates="product")


class Order(BusinessBase):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"), nullable=True)
    order_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)

    customer = relationship("Customer", back_populates="orders")
    sales = relationship("Sale", back_populates="order")


class Sale(BusinessBase):
    __tablename__ = "sales"

    sale_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    revenue = Column(Numeric(12, 2), nullable=False)

    order = relationship("Order", back_populates="sales")
    product = relationship("Product", back_populates="sales")
