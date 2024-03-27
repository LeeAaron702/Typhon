from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import stripe
from database import SessionLocal
from models import Users
from utilities.auth import get_current_user

router = APIRouter()

# Your Stripe secret key should be loaded from an environment variable in production
stripe.api_key = "sk_test_51Oy41HAFxv9Bv1vd7SB59szMp25EygzjKOrSyH87oTpNxCKLwVbWnjsD8mYKrssmU35jG5AbSDAvQnQuyYXgaGpG003cOjZCoe"


class PaymentIntentRequest(BaseModel):
    amount: int
    firstName: str
    lastName: str


class PaymentIntentResponse(BaseModel):
    clientSecret: str
    paymentIntentId: str


class PaymentIntentActionRequest(BaseModel):
    paymentIntentId: str

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/create-payment-intent/", response_model=PaymentIntentResponse)
async def create_payment_intent(
    request: PaymentIntentRequest, 
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    try:
        # Assuming get_current_user returns a user dictionary that includes the username
        username = current_user["username"]
        user = db.query(Users).filter(Users.username == username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        customer_id = user.stripe_customer_id

        # Check if the user already has a Stripe customer ID
        if not customer_id:
            # Create a Stripe customer if one does not exist
            customer = stripe.Customer.create(
                name=f"{request.firstName} {request.lastName}",
                # Additional customer information can go here
            )
            customer_id = customer.id

            # Update the user in the database with the new Stripe customer ID
            user.stripe_customer_id = customer_id
            db.add(user)
            db.commit()

        # Create the payment intent for the existing or new customer
        intent = stripe.PaymentIntent.create(
            amount=request.amount,
            currency="usd",
            capture_method="manual",
            customer=customer_id,  # Use the existing or new customer ID
        )

        return PaymentIntentResponse(
            clientSecret=intent.client_secret, 
            paymentIntentId=intent.id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




@router.post("/capture-payment/")
async def capture_payment(request: PaymentIntentActionRequest):
    try:
        captured_intent = stripe.PaymentIntent.capture(request.paymentIntentId)
        return {"status": captured_intent.status}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail="Failed to capture payment: " + str(e)
        )


@router.post("/cancel-payment/")
async def cancel_payment(request: PaymentIntentActionRequest):
    try:
        canceled_intent = stripe.PaymentIntent.cancel(request.paymentIntentId)
        return {"status": canceled_intent.status}
    except Exception as e:
        raise HTTPException(
            status_code=400, detail="Failed to cancel payment: " + str(e)
        )
