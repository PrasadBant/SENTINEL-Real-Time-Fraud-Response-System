"""
SENTINEL — AI Copilot Route
==============================
POST /api/copilot: simple RAG + intent-parsing chatbot for investigators.
Executes FREEZE/CLOSE actions directly for matching intents; otherwise
delegates to whichever AIProvider app.services.ai_providers.get_provider()
selects (Anthropic/Hugging Face/Mock/... — see AI_PROVIDER in
.env.example), falling back to a canned offline analysis if the live
provider call fails for any reason (missing/invalid key, network error,
rate limit, timeout).
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.actions import handle_action
from app.api.schemas import ActionRequest, CopilotRequest
from app.core.data_store import data_store
from app.core.deps import get_current_user
from app.services.ai_providers import get_provider

router = APIRouter()

_SYSTEM_PROMPT = (
    "You are 'Sentinel AI', an elite, highly professional enterprise fraud intelligence assistant. "
    "Your goal is to provide concise, data-driven, and highly actionable insights to fraud analysts. "
    "Use Markdown formatting (bolding, bullet points) to make your responses extremely engaging and easy to read. "
    "Always maintain a confident, professional, and analytical tone. Keep responses under 150 words."
)


@router.post("/api/copilot")
async def copilot_chat(req: CopilotRequest, user: dict = Depends(get_current_user)) -> dict[str, Any]:
    # 1. Gather Context (RAG)
    context_data = "No specific case selected. The user is asking a general question."
    if req.context_case_id:
        case = data_store.get("cases", {}).get(req.context_case_id)
        if case:
            context_data = f"**Case ID:** {case['case_id']}\n**Status:** {case['status']}\n**Risk Level:** {case.get('risk_level', 0)}%\n"
            # Add transaction context
            tx_ids = case.get("transactions", [])
            txs = [data_store.get("transactions", {}).get(t) for t in tx_ids if t in data_store.get("transactions", {})]
            if txs:
                context_data += f"**Transactions involved:** {len(txs)}\n"
                context_data += "**Latest Transaction Details:**\n"
                latest_tx = txs[0]
                context_data += f"- Amount: {latest_tx.get('amount', 0)} INR\n"
                context_data += f"- Sender: {latest_tx.get('sender_account', 'Unknown')}\n"
                context_data += f"- Receiver: {latest_tx.get('receiver_account', 'Unknown')}\n"
                context_data += f"- Type: {latest_tx.get('type', 'N/A')}\n"

    # 2. Check Intent for Tool Calling
    user_msg = req.message.lower()
    action_taken = None
    reply = ""

    # Simple intent parsing for Hackathon demo.
    # SECURITY: these intents execute real investigative actions (freeze/close)
    # via handle_action() directly, bypassing the /action/* routes' own
    # require_role("admin") dependency — so the same check must happen here,
    # or a viewer could freeze/close a case just by asking the chatbot to.
    is_admin = user.get("role") == "admin"
    if "freeze" in user_msg and req.context_case_id:
        if not is_admin:
            reply = "🔒 **Access denied.** Freezing accounts requires admin privileges — you're logged in as a viewer."
        else:
            # Execute FREEZE Tool
            action_payload = ActionRequest(case_id=req.context_case_id, target_id="GLOBAL", reason="AI Copilot Action")
            await handle_action("freeze", action_payload)
            reply = f"✅ **Action Executed:** I have applied a **FREEZE** on all accounts associated with Case `{req.context_case_id}` to prevent further fund movement."
            action_taken = {"type": "FREEZE_ACCOUNTS", "case_id": req.context_case_id}
    elif "close" in user_msg and req.context_case_id:
        if not is_admin:
            reply = "🔒 **Access denied.** Closing a case requires admin privileges — you're logged in as a viewer."
        else:
            action_payload = ActionRequest(case_id=req.context_case_id, reason="AI Copilot closed")
            await handle_action("close", action_payload)
            reply = f"✅ **Action Executed:** Case `{req.context_case_id}` has been **closed** and marked as resolved."
            action_taken = {"type": "CLOSE_CASE", "case_id": req.context_case_id}
    else:
        provider_success = False
        try:
            provider = get_provider()
            reply = await provider.generate(
                system_prompt=_SYSTEM_PROMPT,
                user_message=req.message,
                context=context_data,
            )
            provider_success = bool(reply)
        except Exception as e:
            # Fallback on failure (e.g., DNS error, proxy block, timeout, rate
            # limit, bad/missing API key, or an unimplemented stub provider).
            print(f"[Copilot Warning] AI provider failed: {e}. Falling back to local AI.")
            provider_success = False

        if not provider_success:
            # High-quality dynamic simulator for offline fallback/missing token
            case_id = req.context_case_id or "UNKNOWN"
            if req.context_case_id and req.context_case_id in data_store.get("cases", {}):
                case = data_store["cases"][req.context_case_id]
                risk = case.get("risk_level", 50)
                tx_ids = case.get("transactions", [])
                txs = [data_store.get("transactions", {}).get(t) for t in tx_ids if t in data_store.get("transactions", {})]
                amount = txs[0].get("amount", 0.0) if txs else 0.0
                sender = txs[0].get("sender_account", "N/A") if txs else "N/A"
                receiver = txs[0].get("receiver_account", "N/A") if txs else "N/A"

                if risk >= 70:
                    reply = f"**[Sentinel Offline AI]** Analysis of Case `{case_id}` indicates **high-risk** activity (Risk: {risk}%). \n\nThe transaction of **{amount} INR** from `{sender}` to `{receiver}` shows strong patterns of mule routing. \n\nI recommend freezing the destination account and alerting the recipient bank immediately."
                else:
                    reply = f"**[Sentinel Offline AI]** Case `{case_id}` exhibits **moderate risk** indicators (Risk: {risk}%). \n\nThe transaction of **{amount} INR** from `{sender}` to `{receiver}` deviates from the sender's average historical velocity. \n\nI recommend placing the receiver account on monitoring and reviewing further hops."
            else:
                msg_lower = req.message.lower()
                if "what" in msg_lower and "sentinel" in msg_lower:
                    reply = "**[Sentinel Offline AI]** Sentinel is a Real-Time Fraud Response System. It monitors transactions, constructs behavioral graphs, and applies machine learning to detect and mitigate fraudulent activities instantaneously."
                elif "how" in msg_lower and "freeze" in msg_lower:
                    reply = "**[Sentinel Offline AI]** To freeze a suspect account, select a case from the dashboard and use the **FREEZE** action. This will simulate an API call to the destination bank to hold the funds."
                elif "hello" in msg_lower or "hi" in msg_lower:
                    reply = "**[Sentinel Offline AI]** Hello! I am Sentinel's AI Copilot. I am currently running in offline mode. Please select a specific case from the graph for me to analyze, or ask me general questions about Sentinel."
                elif "fix" in msg_lower:
                    reply = "**[Sentinel Offline AI]** To fix network restrictions and restore the live HuggingFace AI engine, ensure your firewall allows outbound connections to `api-inference.huggingface.co`. In the meantime, I am fully capable of answering basic questions locally!"
                else:
                    reply = f"**[Sentinel Offline AI]** I am currently running in offline mode due to network restrictions. \n\nPlease select a specific case from the graph to analyze, or ask me basic questions about Sentinel. Restore the live HuggingFace AI engine for full dynamic capabilities."

    return {"reply": reply, "action": action_taken}
