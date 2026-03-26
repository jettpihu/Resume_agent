from uagents import Agent, Context
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
from datetime import datetime, timezone
from uuid import uuid4
import os
import asyncio

# Hardcode the agent's expected destination address (or pass it dynamically)
# We will use addressing by endpoint since we are running locally on port 8000
DESTINATION_AGENT = "http://127.0.0.1:8000/submit"

client_agent = Agent(
    name="user_client",
    port=8001,
    endpoint=["http://127.0.0.1:8001/submit"],
)

from agent import agent as target_agent

@client_agent.on_event("startup")
async def send_message(ctx: Context):
    # Wait slightly to ensure local network routing is up
    await asyncio.sleep(1)
    print("\n--- Local Chat Interface ---")
    message = input("You: ")
    msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=message)]
    )
    
    # Dynamically fetch the real address of your agent from agent.py!
    target_address = target_agent.address
    
    await ctx.send(target_address, msg)
    ctx.logger.info(f"Message sent to Resume Agent!")

@client_agent.on_message(model=ChatMessage)
async def handle_response(ctx: Context, sender: str, msg: ChatMessage):
    response_text = "".join([str(getattr(item, "text", "")) for item in msg.content])
    print(f"\n[Resume Agent]: {response_text}\nYou: ", end="")
    
    # Prompt for the next reply
    await asyncio.sleep(0.5)
    reply = input()
    if reply.lower() in ["exit", "quit"]:
        os._exit(0)
        
    next_msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=reply)]
    )
    await ctx.send(sender, next_msg)

if __name__ == "__main__":
    print("Starting local chat client... Press CTRL+C to stop.")
    client_agent.run()
