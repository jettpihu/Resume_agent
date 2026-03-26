from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    Funds,
    payment_protocol_spec,
    CommitPayment, CompletePayment, CancelPayment, RejectPayment
)
import os

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")
FET_FUNDS = Funds(currency="FET", amount="0.1", payment_method="fet_direct")

def is_premium_user(ctx: Context, sender: str) -> bool:
    """Check if sender has unlocked premium features via storage cache"""
    return bool(ctx.storage.get(f"premium_{sender}"))

@payment_proto.on_message(CommitPayment)
async def handle_payment(ctx: Context, sender: str, msg: CommitPayment):
    # Simulated validation layer (like in secure insurance agent)
    payment_valid = True # Verify cosmpy tx hash here
    
    if payment_valid:
        ctx.storage.set(f"premium_{sender}", True)
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))
    else:
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason="Invalid Tx"))

@payment_proto.on_message(RejectPayment)
async def handle_reject(ctx: Context, sender: str, msg: RejectPayment):
    pass
