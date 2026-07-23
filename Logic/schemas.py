from pydantic import BaseModel, Field
from typing import List, Optional


#  Pydantic models 

class PaymentCreate(BaseModel):
    amount: float
    type: str = "payment"          # 'payment' | 'refund' | 'credit_applied'
    date: Optional[str] = None     # YYYY-MM-DD; defaults to today
    note: Optional[str] = None

class CreditApply(BaseModel):
    source_invoice: int
    target_invoice: int
    amount: float

class BulkPaymentItem(BaseModel):
    invoice_number: int
    amount: float
    note: Optional[str] = None

class BulkPaymentRequest(BaseModel):
    allocations: List[BulkPaymentItem]
    date: Optional[str] = None

class CustomerBase(BaseModel):
    name: str
    default_tier: str

class CustomerCreate(CustomerBase):
    phone_number: Optional[str] = None

class Customer(CustomerBase):
    customer_id: int
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    item_name: str
    retail_price: float
    wholesale_price: float
    stock_quantity: Optional[int] = None
    cost: float

class Product(ProductBase):
    product_id: int
    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    product_id: int
    item_name: str
    retail_price: float
    wholesale_price: float
    cost: float
    stock_quantity: Optional[int] = None

class ProductUpdate(BaseModel):
    item_name: Optional[str] = None
    retail_price: Optional[float] = None
    wholesale_price: Optional[float] = None
    cost: Optional[float] = None
    stock_quantity: Optional[int] = None

class CartItem(BaseModel):
    product_id: int
    quantity: int

class InvoiceRequest(BaseModel):
    customer_id: int
    customer_name: str
    tier_choice: str
    order_items: List[CartItem]
    quantity_type: str
    bill_type: str
    discount_input: str = "0"
    apply_tax: bool = True
    return_invoice_number: Optional[str] = None
    amount_paid_now: Optional[float] = Field(default=None, ge=0)

class ReturnRequest(BaseModel):
    invoice_number: int

#  Expense models 

class ExpenseCreate(BaseModel):
    category: str
    description: str
    amount: float
    date: str                    # "YYYY-MM-DD"
    notes: Optional[str] = None

#  Worker models 

class WorkerCreate(BaseModel):
    name: str
    base_salary: float = Field(ge=0, description="Weekly base salary, cannot be negative")

class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    base_salary: Optional[float] = Field(default=None, ge=0)
    active: Optional[int] = None

class LedgerEntryCreate(BaseModel):
    type: str                    # "salary" | "bonus" | "deduction"
    amount: float
    note: Optional[str] = None
    date: Optional[str] = None   # defaults to today if omitted

class CashoutCreate(BaseModel):
    note: Optional[str] = None
