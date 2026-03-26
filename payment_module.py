from decimal import Decimal, InvalidOperation

from uagents import Context, Protocol
from uagents_core.contrib.protocols.payment import (
    Funds,
    payment_protocol_spec,
    CommitPayment, CompletePayment, CancelPayment, RejectPayment
)
from uagents_core.contrib.protocols.payment import RequestPayment

_agent_wallet = None
_on_payment_verified = None


def set_agent_wallet(wallet):
    global _agent_wallet
    _agent_wallet = wallet


def set_on_payment_verified(callback):
    """
    Register async callback: callback(ctx, sender) after verified payment.
    """
    global _on_payment_verified
    _on_payment_verified = callback

payment_proto = Protocol(spec=payment_protocol_spec, role="seller")
FET_FUNDS = Funds(currency="FET", amount="0.1", payment_method="fet_direct")
EDIT_FET_FUNDS = Funds(currency="FET", amount="0.01", payment_method="fet_direct")

def is_premium_user(ctx: Context, sender: str) -> bool:
    """Check if sender has unlocked premium features via storage cache"""
    return bool(ctx.storage.get(f"premium_{sender}"))


def is_edit_unlocked(ctx: Context, sender: str) -> bool:
    """Check if sender has paid for resume editing."""
    return bool(ctx.storage.get(f"edit_unlocked_{sender}"))


async def request_edit_payment_from_user(ctx: Context, user_address: str) -> None:
    session = str(ctx.session)
    use_testnet = True
    fet_network = "stable-testnet" if use_testnet else "mainnet"
    metadata = {
        "agent": "career_resume_agent",
        "service": "resume_edit",
        "feature": "resume_edit",
        "fet_network": fet_network,
        "mainnet": "false" if use_testnet else "true",
    }
    if _agent_wallet:
        recipient_addr = str(_agent_wallet.address())
        metadata["provider_agent_wallet"] = recipient_addr
    else:
        recipient_addr = str(ctx.agent.address)

    payment_request = RequestPayment(
        accepted_funds=[EDIT_FET_FUNDS],
        recipient=recipient_addr,
        deadline_seconds=300,
        reference=session,
        description="Resume Edit Unlock (0.01 FET)",
        metadata=metadata,
    )
    await ctx.send(user_address, payment_request)
    ctx.logger.info(
        f"payment_request_sent user={user_address} recipient={recipient_addr} reference={session} funds=0.01 FET"
    )

@payment_proto.on_message(CommitPayment)
async def handle_payment(ctx: Context, sender: str, msg: CommitPayment):
    # Simulated validation layer (replace with real on-chain verification if needed).
    payment_valid = True

    try:
        ctx.logger.info(
            f"payment_commit_received sender={sender} tx={getattr(msg, 'transaction_id', '')}"
        )
        if not payment_valid:
            await ctx.send(
                sender,
                CancelPayment(
                    transaction_id=getattr(msg, "transaction_id", ""),
                    reason="Invalid transaction",
                ),
            )
            return

        funds = getattr(msg, "funds", None)
        if not funds:
            await ctx.send(
                sender,
                CancelPayment(
                    transaction_id=getattr(msg, "transaction_id", ""),
                    reason="Missing payment funds payload",
                ),
            )
            return

        try:
            amount = Decimal(str(getattr(funds, "amount", "0")))
        except (InvalidOperation, TypeError, ValueError):
            await ctx.send(
                sender,
                CancelPayment(
                    transaction_id=getattr(msg, "transaction_id", ""),
                    reason="Invalid payment amount",
                ),
            )
            return

        method = str(getattr(funds, "payment_method", ""))
        currency = str(getattr(funds, "currency", ""))
        if method != "fet_direct" or currency != "FET":
            await ctx.send(
                sender,
                CancelPayment(
                    transaction_id=getattr(msg, "transaction_id", ""),
                    reason=f"Unsupported payment: {currency}/{method}",
                ),
            )
            return

        if amount >= Decimal("0.01"):
            ctx.storage.set(f"edit_unlocked_{sender}", True)
        if amount >= Decimal("0.1"):
            ctx.storage.set(f"premium_{sender}", True)

        ctx.logger.info(
            f"payment_commit_verified sender={sender} amount={amount} currency={currency} method={method}"
        )

        await ctx.send(
            sender,
            CompletePayment(transaction_id=getattr(msg, "transaction_id", "")),
        )
        if _on_payment_verified is not None:
            await _on_payment_verified(ctx, sender)
    except Exception as e:
        ctx.logger.exception("payment_commit_handler_failed")
        await ctx.send(
            sender,
            CancelPayment(
                transaction_id=getattr(msg, "transaction_id", ""),
                reason=f"Payment handler error: {e}",
            ),
        )

@payment_proto.on_message(RejectPayment)
async def handle_reject(ctx: Context, sender: str, msg: RejectPayment):
    ctx.logger.info(f"payment_rejected_by={sender} reason={getattr(msg, 'reason', '')}")
