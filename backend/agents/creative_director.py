"""
Creative Director Agent - WEBSITE ASSISTANT v3.0
=================================================
Guides natural conversation to extract all 4 commercial brief cards.

Features:
- Tracks card completion progress
- Suggests next steps naturally
- Synthesizes partial information
- Triggers checkout when ready
- Maintains conversation context

pip install anthropic pydantic structlog
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Literal, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger().bind(agent="creative_director")


# =============================================================================
# CARD COMPLETION STATUS
# =============================================================================

class CardStatus(str, Enum):
    """Status of each card in the flow"""
    MISSING = "missing"
    PARTIAL = "partial"
    COMPLETE = "complete"


class CardProgress(BaseModel):
    """Progress tracking for all 4 cards"""
    persona: CardStatus = CardStatus.MISSING
    competitor: CardStatus = CardStatus.MISSING
    script: CardStatus = CardStatus.MISSING
    roi: CardStatus = CardStatus.MISSING
    
    @property
    def complete_count(self) -> int:
        return sum(1 for s in [self.persona, self.competitor, self.script, self.roi] 
                   if s == CardStatus.COMPLETE)
    
    @property
    def all_complete(self) -> bool:
        return self.complete_count == 4
    
    @property
    def progress_percent(self) -> int:
        return int((self.complete_count / 4) * 100)
    
    def get_next_missing(self) -> Optional[str]:
        """Get the next card that needs attention"""
        priority_order = ["persona", "competitor", "script", "roi"]
        for card in priority_order:
            if getattr(self, card) != CardStatus.COMPLETE:
                return card
        return None


# =============================================================================
# CONVERSATION CONTEXT
# =============================================================================

class ConversationContext(BaseModel):
    """Accumulated context from conversation"""
    
    # Business info (gathered throughout)
    business_name: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    
    # Contact info
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    
    # Persona info
    target_audience: Optional[str] = None
    pain_points: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    
    # Competitor info
    competitors: List[str] = Field(default_factory=list)
    differentiators: List[str] = Field(default_factory=list)
    
    # Script info
    tone: Optional[str] = None
    duration: Optional[int] = None
    key_message: Optional[str] = None
    
    # ROI info
    budget: Optional[int] = None
    expected_results: Optional[str] = None


# =============================================================================
# GUIDANCE TEMPLATES
# =============================================================================

GUIDANCE_TEMPLATES = {
    "persona": {
        "intro": "Let's start by understanding your target audience.",
        "questions": [
            "Who is your ideal customer? What's their job title?",
            "What industry are they in?",
            "What's their biggest challenge right now?",
        ],
        "follow_up": "Tell me more about their day-to-day struggles.",
        "transition": "Great persona insight! Now let's look at your competition.",
    },
    "competitor": {
        "intro": "Understanding your competitive landscape is crucial.",
        "questions": [
            "Who are your main competitors?",
            "What do they do well that you need to match?",
            "What's your key advantage over them?",
        ],
        "follow_up": "Any specific competitor you want to focus on?",
        "transition": "Perfect competitive intel! Now let's craft your story.",
    },
    "script": {
        "intro": "Time to craft a compelling narrative.",
        "questions": [
            "What's the main benefit you want to highlight?",
            "What action do you want viewers to take?",
            "What tone fits your brand - professional, casual, urgent?",
        ],
        "follow_up": "How long should the video be - 30, 60, or 90 seconds?",
        "transition": "Love the script direction! Last step - let's talk ROI.",
    },
    "roi": {
        "intro": "Let's make sure this investment makes sense.",
        "questions": [
            "What's your budget for this commercial?",
            "What results would make this a success?",
            "How will you measure ROI?",
        ],
        "follow_up": "What's your timeline for seeing results?",
        "transition": "Your commercial brief is complete! Ready to proceed?",
    },
}

COMPLETION_CELEBRATION = """
🎉 **Your Commercial Brief is Complete!**

Here's what we've built together:

• **Target Persona:** {persona_summary}
• **Key Differentiator:** {differentiator}
• **Format:** {duration}-second {tone} commercial
• **Investment:** ${budget:,}
• **Projected ROI:** {roi_projection}

Everything looks great! Click below to proceed to checkout and we'll start 
producing your video immediately.
"""

PROGRESS_INDICATOR = """
📊 **Progress: {complete}/4 cards complete**
{progress_bar}
{status_line}
"""


# =============================================================================
# CREATIVE DIRECTOR AGENT
# =============================================================================

class CreativeDirectorAgent:
    """
    Orchestrates the commercial creation conversation.
    
    Responsibilities:
    1. Track which cards are complete
    2. Extract relevant info from any message
    3. Guide user naturally toward missing info
    4. Synthesize partial information into cards
    5. Trigger checkout when all 4 cards ready
    """
    
    def __init__(self, anthropic_client=None):
        self.client = anthropic_client
        self._logger = logger.bind(component="creative_director_agent")
    
    async def process(
        self,
        message: str,
        current_state: Dict[str, Any],
        card_progress: CardProgress,
    ) -> Dict[str, Any]:
        """
        Process user message and determine next action.
        
        Returns:
            Dict with:
            - response: str (what to say)
            - next_node: str (where to route)
            - context_updates: Dict (extracted info)
            - card_progress: CardProgress (updated)
        """
        self._logger.info("processing_message", 
                         message_length=len(message),
                         progress=card_progress.complete_count)
        
        # Extract any relevant context from message
        context_updates = await self._extract_context(message, current_state)
        
        # Update card progress based on state
        card_progress = self._update_progress(current_state, context_updates)
        
        # Check if all cards complete
        if card_progress.all_complete:
            return await self._handle_completion(current_state, card_progress)
        
        # Determine next guidance
        return await self._generate_guidance(
            message, current_state, card_progress, context_updates
        )
    
    async def _extract_context(
        self, 
        message: str, 
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract relevant business context from message"""
        
        updates = {}
        msg_lower = message.lower()
        
        # Simple pattern extraction (could be enhanced with LLM)
        
        # Budget detection
        import re
        budget_match = re.search(r'\$?([\d,]+)(?:k|K)?', message)
        if budget_match:
            amount = budget_match.group(1).replace(',', '')
            if 'k' in message.lower() or 'K' in message:
                amount = int(amount) * 1000
            else:
                amount = int(amount)
            if amount >= 500:  # Reasonable budget threshold
                updates["budget"] = amount
        
        # Duration detection
        for duration in [15, 30, 60, 90, 120]:
            if f"{duration} second" in msg_lower or f"{duration}s" in msg_lower:
                updates["duration"] = duration
                break
        
        # Tone detection
        tones = ["professional", "casual", "urgent", "inspirational", "playful"]
        for tone in tones:
            if tone in msg_lower:
                updates["tone"] = tone
                break
        
        # Email detection
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', message)
        if email_match:
            updates["user_email"] = email_match.group()
        
        # Competitor detection (simple keyword matching)
        competitor_keywords = ["hubspot", "marketo", "salesforce", "mailchimp", 
                              "wistia", "vidyard", "loom", "synthesia", "heygen"]
        found_competitors = [c for c in competitor_keywords if c in msg_lower]
        if found_competitors:
            existing = current_state.get("competitors", [])
            updates["competitors"] = list(set(existing + found_competitors))
        
        return updates
    
    def _update_progress(
        self,
        current_state: Dict[str, Any],
        context_updates: Dict[str, Any]
    ) -> CardProgress:
        """Update card progress based on current state"""
        
        progress = CardProgress()
        
        # Check persona card
        if current_state.get("persona_card"):
            progress.persona = CardStatus.COMPLETE
        elif current_state.get("director", {}).get("persona_context"):
            progress.persona = CardStatus.PARTIAL
        
        # Check competitor card
        if current_state.get("competitor_card"):
            progress.competitor = CardStatus.COMPLETE
        elif current_state.get("director", {}).get("competitor_context"):
            progress.competitor = CardStatus.PARTIAL
        
        # Check script card
        if current_state.get("script_card"):
            progress.script = CardStatus.COMPLETE
        elif current_state.get("director", {}).get("script_context"):
            progress.script = CardStatus.PARTIAL
        
        # Check ROI card
        if current_state.get("roi_card"):
            progress.roi = CardStatus.COMPLETE
        elif context_updates.get("budget"):
            progress.roi = CardStatus.PARTIAL
        
        return progress
    
    async def _handle_completion(
        self,
        current_state: Dict[str, Any],
        card_progress: CardProgress
    ) -> Dict[str, Any]:
        """Handle all 4 cards complete - trigger checkout"""
        
        self._logger.info("all_cards_complete", triggering_checkout=True)
        
        # Build completion message
        persona = current_state.get("persona_card", {})
        script = current_state.get("script_card", {})
        roi = current_state.get("roi_card", {})
        
        response = COMPLETION_CELEBRATION.format(
            persona_summary=persona.get("persona_name", "Your ideal customer"),
            differentiator=current_state.get("director", {}).get("competitor_context", {}).get("key_advantage", "Your unique value"),
            duration=script.get("estimated_duration_seconds", 60),
            tone=script.get("tone", "professional"),
            budget=roi.get("investment_amount", 5000),
            roi_projection=f"{roi.get('roi_percentage', 1000)}%",
        )
        
        return {
            "response": response,
            "next_node": "checkout",
            "cards_ready": True,
            "card_progress": card_progress,
            "context_updates": {},
        }
    
    async def _generate_guidance(
        self,
        message: str,
        current_state: Dict[str, Any],
        card_progress: CardProgress,
        context_updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate natural guidance toward next card"""
        
        next_card = card_progress.get_next_missing()
        templates = GUIDANCE_TEMPLATES.get(next_card, {})
        
        # Build progress indicator
        progress_bar = self._build_progress_bar(card_progress)
        
        # Determine appropriate guidance
        if card_progress.complete_count == 0:
            # First card - use intro
            guidance = templates.get("intro", "Let's get started!")
            question = templates.get("questions", ["Tell me about your business."])[0]
            response = f"{guidance}\n\n{question}"
        else:
            # Subsequent cards - use transition from previous
            prev_card = self._get_previous_card(next_card)
            prev_templates = GUIDANCE_TEMPLATES.get(prev_card, {})
            transition = prev_templates.get("transition", "Great progress!")
            question = templates.get("questions", ["What's next?"])[0]
            response = f"{transition}\n\n{question}"
        
        # Add progress indicator
        status_line = f"Next: {next_card.title()} card"
        progress_section = PROGRESS_INDICATOR.format(
            complete=card_progress.complete_count,
            progress_bar=progress_bar,
            status_line=status_line
        )
        
        # Determine routing
        node_map = {
            "persona": "persona",
            "competitor": "intelligence",
            "script": "script",
            "roi": "roi",
        }
        next_node = node_map.get(next_card, "website_assistant")
        
        return {
            "response": response,
            "next_node": next_node,
            "cards_ready": False,
            "card_progress": card_progress,
            "context_updates": context_updates,
            "progress_indicator": progress_section,
        }
    
    def _build_progress_bar(self, progress: CardProgress) -> str:
        """Build visual progress bar"""
        cards = [
            ("P", progress.persona),
            ("C", progress.competitor),
            ("S", progress.script),
            ("R", progress.roi),
        ]
        
        bar = ""
        for label, status in cards:
            if status == CardStatus.COMPLETE:
                bar += f"[✅{label}]"
            elif status == CardStatus.PARTIAL:
                bar += f"[🔄{label}]"
            else:
                bar += f"[⬜{label}]"
        
        return bar
    
    def _get_previous_card(self, current: str) -> str:
        """Get the card before current in sequence"""
        sequence = ["persona", "competitor", "script", "roi"]
        idx = sequence.index(current)
        return sequence[idx - 1] if idx > 0 else "persona"
    
    async def synthesize_context(
        self,
        conversation_history: List[Dict[str, str]],
        current_context: ConversationContext
    ) -> ConversationContext:
        """
        Use LLM to synthesize conversation into structured context.
        Called when user provides information organically.
        """
        if not self.client:
            return current_context
        
        # Build conversation summary
        history_text = "\n".join([
            f"{msg['role'].upper()}: {msg['content']}"
            for msg in conversation_history[-10:]  # Last 10 messages
        ])
        
        prompt = f"""Analyze this conversation and extract business context.

CONVERSATION:
{history_text}

CURRENT CONTEXT:
{current_context.model_dump_json(indent=2)}

Extract any NEW information about:
- Business name, industry, company size
- Target audience, their pain points, goals
- Competitors mentioned, differentiators
- Preferred tone, duration, key message
- Budget, expected results

Return JSON only with updated fields (omit unchanged fields):
"""
        
        try:
            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            result = json.loads(response.content[0].text)
            
            # Merge updates
            for key, value in result.items():
                if value and hasattr(current_context, key):
                    if isinstance(getattr(current_context, key), list):
                        existing = getattr(current_context, key)
                        if isinstance(value, list):
                            setattr(current_context, key, list(set(existing + value)))
                    else:
                        setattr(current_context, key, value)
            
            return current_context
            
        except Exception as e:
            self._logger.error("synthesis_failed", error=str(e))
            return current_context


# =============================================================================
# LANGGRAPH NODE FUNCTION
# =============================================================================

async def creative_director_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node for Creative Director.
    
    Called after any card generation to:
    1. Update progress tracking
    2. Generate next guidance
    3. Route appropriately
    """
    from langchain_core.messages import AIMessage
    
    # Initialize agent
    agent = CreativeDirectorAgent()
    
    # Get last user message
    messages = state.get("messages", [])
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            last_user_msg = msg.content
            break
        elif isinstance(msg, dict) and msg.get('role') == 'user':
            last_user_msg = msg.get('content', '')
            break
    
    # Build card progress from state
    card_progress = CardProgress(
        persona=CardStatus.COMPLETE if state.get("persona_card") else CardStatus.MISSING,
        competitor=CardStatus.COMPLETE if state.get("competitor_card") else CardStatus.MISSING,
        script=CardStatus.COMPLETE if state.get("script_card") else CardStatus.MISSING,
        roi=CardStatus.COMPLETE if state.get("roi_card") else CardStatus.MISSING,
    )
    
    # Process
    result = await agent.process(
        message=last_user_msg,
        current_state=state,
        card_progress=card_progress,
    )
    
    # Build response
    updates = {
        "current_node": "creative_director",
        "next_node": result["next_node"],
        "cards_ready": result.get("cards_ready", False),
        "hop_count": state.get("hop_count", 0) + 1,
    }
    
    # Add response message if provided
    if result.get("response"):
        updates["messages"] = [AIMessage(content=result["response"])]
    
    # Update director state with progress
    director = dict(state.get("director", {}))
    director["card_progress"] = card_progress.model_dump()
    updates["director"] = director
    
    return updates


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CreativeDirectorAgent",
    "CardStatus",
    "CardProgress",
    "ConversationContext",
    "creative_director_node",
]


# =============================================================================
# DEMO
# =============================================================================

async def demo():
    """Demo the Creative Director agent"""
    
    print("=" * 70)
    print("CREATIVE DIRECTOR AGENT DEMO")
    print("=" * 70)
    
    agent = CreativeDirectorAgent()
    
    # Simulate conversation progression
    states = [
        {"messages": [], "director": {}},  # Start
        {"messages": [], "director": {}, "persona_card": {"name": "Marketing Maria"}},  # After persona
        {"messages": [], "director": {}, "persona_card": {"name": "Marketing Maria"}, 
         "competitor_card": {"competitor": "HubSpot"}},  # After competitor
        {"messages": [], "director": {}, "persona_card": {"name": "Marketing Maria"},
         "competitor_card": {"competitor": "HubSpot"},
         "script_card": {"duration": 60}},  # After script
        {"messages": [], "director": {}, "persona_card": {"name": "Marketing Maria"},
         "competitor_card": {"competitor": "HubSpot"},
         "script_card": {"duration": 60},
         "roi_card": {"budget": 5000}},  # All complete
    ]
    
    messages = [
        "I want to create a commercial",
        "We target marketing managers",
        "Our main competitor is HubSpot",
        "Make it 60 seconds, professional tone",
        "Budget is $5000",
    ]
    
    for i, (msg, state) in enumerate(zip(messages, states)):
        print(f"\n--- Turn {i+1} ---")
        print(f"USER: {msg}")
        
        progress = CardProgress(
            persona=CardStatus.COMPLETE if state.get("persona_card") else CardStatus.MISSING,
            competitor=CardStatus.COMPLETE if state.get("competitor_card") else CardStatus.MISSING,
            script=CardStatus.COMPLETE if state.get("script_card") else CardStatus.MISSING,
            roi=CardStatus.COMPLETE if state.get("roi_card") else CardStatus.MISSING,
        )
        
        result = await agent.process(msg, state, progress)
        
        print(f"PROGRESS: {result['card_progress'].complete_count}/4 cards")
        print(f"NEXT NODE: {result['next_node']}")
        print(f"RESPONSE: {result['response'][:200]}...")
        
        if result.get("cards_ready"):
            print("\n🎉 ALL CARDS COMPLETE - TRIGGERING CHECKOUT!")
            break


if __name__ == "__main__":
    asyncio.run(demo())
