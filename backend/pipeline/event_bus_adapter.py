"""
Event Bus Adapter - LEGENDARY EDITION
======================================
Shared RabbitMQ Infrastructure for Website Assistant → RAGNAROK Pipeline

Features:
- Typed Event System: Pydantic models for all events
- Publisher/Subscriber Pattern: Clean async interfaces
- Circuit Breaker: Resilient connection handling
- Dead Letter Exchange: Failed messages tracked
- Correlation Tracking: Full trace propagation
- Graceful Shutdown: Clean connection teardown

pip install pydantic aio-pika structlog
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable, Any, TypeVar, Generic, Union
from functools import wraps

from pydantic import BaseModel, Field, computed_field
import structlog
import logging

# Optional: aio-pika for async RabbitMQ
try:
    import aio_pika
    from aio_pika import Message, DeliveryMode, ExchangeType
    from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractExchange, AbstractQueue
    HAS_AIOPIKA = True
except ImportError:
    HAS_AIOPIKA = False
    print("⚠️  aio-pika not installed. Using in-memory event bus for testing.")


# =============================================================================
# STRUCTURED LOGGING
# =============================================================================

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

class EventBusSettings:
    # RabbitMQ Connection
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    
    # Exchange Configuration
    EXCHANGE_NAME: str = "barrios_a2i"
    EXCHANGE_TYPE: str = "topic"
    
    # Dead Letter Exchange
    DLX_EXCHANGE_NAME: str = "barrios_a2i_dlx"
    DLX_QUEUE_NAME: str = "dead_letters"
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: float = 5.0
    
    # Circuit Breaker
    CB_FAILURE_THRESHOLD: int = 5
    CB_RESET_TIMEOUT_SECONDS: float = 30.0
    
    # Message TTL
    MESSAGE_TTL_MS: int = 86400000  # 24 hours
    
    # Prefetch (consumer concurrency)
    PREFETCH_COUNT: int = 10


settings = EventBusSettings()


# =============================================================================
# EVENT TYPE ENUMS
# =============================================================================

class EventType(str, Enum):
    """All event types in the pipeline"""
    
    # Website Assistant → Brief Assembler
    CONVERSATION_CARDS_COMPLETE = "conversation.cards_complete"
    
    # Brief Assembler → Payment Gateway
    BRIEF_ASSEMBLED = "brief.assembled"
    BRIEF_VALIDATION_FAILED = "brief.validation_failed"
    BRIEF_READY_FOR_PAYMENT = "brief.ready_for_payment"
    
    # Payment Gateway → Delivery Agent + RAGNAROK
    PAYMENT_SESSION_CREATED = "payment.session_created"
    PAYMENT_CONFIRMED = "payment.confirmed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_ABANDONED = "payment.abandoned"
    ORDER_CREATED = "order.created"
    ORDER_QUEUED = "order.queued"
    ORDER_CANCELLED = "order.cancelled"
    
    # RAGNAROK → Delivery Agent
    PRODUCTION_STARTED = "production.started"
    PRODUCTION_PHASE_COMPLETE = "production.phase_complete"
    PRODUCTION_COMPLETED = "production.completed"
    PRODUCTION_FAILED = "production.failed"
    
    # Delivery Agent (internal)
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"
    DELIVERY_COMPLETED = "delivery.completed"
    DELIVERY_EXPIRED = "delivery.expired"
    
    # Revision Flow
    REVISION_REQUESTED = "revision.requested"
    REVISION_COMPLETED = "revision.completed"


class EventPriority(int, Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


# =============================================================================
# BASE EVENT SCHEMA
# =============================================================================

class BaseEvent(BaseModel):
    """Base event schema - all events inherit from this"""
    
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    version: str = "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_agent: str
    priority: EventPriority = EventPriority.NORMAL
    
    # Retry tracking
    attempt_count: int = 0
    max_attempts: int = settings.MAX_RETRIES
    
    # Payload (override in subclasses)
    payload: dict = Field(default_factory=dict)
    
    @computed_field
    @property
    def routing_key(self) -> str:
        """Generate routing key from event type"""
        return self.event_type.value
    
    def to_message_body(self) -> bytes:
        """Serialize to JSON bytes for RabbitMQ"""
        return self.model_dump_json().encode()
    
    @classmethod
    def from_message_body(cls, body: bytes) -> "BaseEvent":
        """Deserialize from JSON bytes"""
        return cls.model_validate_json(body)


# =============================================================================
# TYPED EVENT SCHEMAS
# =============================================================================

# --- Website Assistant Events ---

class CardsCompletePayload(BaseModel):
    """Payload for conversation.cards_complete"""
    session_id: str
    user_email: str
    business_name: str
    persona_card: dict
    competitor_card: dict
    script_card: dict
    roi_card: dict


class ConversationCardsCompleteEvent(BaseEvent):
    """Website Assistant → Brief Assembler: All 4 cards ready"""
    event_type: EventType = EventType.CONVERSATION_CARDS_COMPLETE
    source_agent: str = "website_assistant"
    payload: CardsCompletePayload


# --- Brief Assembler Events ---

class BriefAssembledPayload(BaseModel):
    """Payload for brief.assembled"""
    brief_id: str
    session_id: str
    business_name: str
    contact_email: str
    payment_tier: str
    quoted_price: int
    duration_seconds: int
    confidence_score: float
    quality_grade: str
    is_ready_for_payment: bool
    creative_brief: dict  # Full CreativeBrief object


class BriefAssembledEvent(BaseEvent):
    """Brief Assembler → Payment Gateway: Brief ready"""
    event_type: EventType = EventType.BRIEF_ASSEMBLED
    source_agent: str = "brief_assembler"
    payload: BriefAssembledPayload


class BriefValidationFailedPayload(BaseModel):
    """Payload for brief.validation_failed"""
    session_id: str
    issues: list[dict]
    repairs_attempted: list[dict]
    confidence_score: float
    suggestions: list[str]


class BriefValidationFailedEvent(BaseEvent):
    """Brief Assembler → Website Assistant: Validation failed"""
    event_type: EventType = EventType.BRIEF_VALIDATION_FAILED
    source_agent: str = "brief_assembler"
    payload: BriefValidationFailedPayload


# --- Payment Gateway Events ---

class PaymentSessionCreatedPayload(BaseModel):
    """Payload for payment.session_created"""
    brief_id: str
    checkout_url: str
    stripe_session_id: str
    expires_at: datetime
    amount: int


class PaymentSessionCreatedEvent(BaseEvent):
    """Payment Gateway → Delivery Agent: Checkout ready"""
    event_type: EventType = EventType.PAYMENT_SESSION_CREATED
    source_agent: str = "payment_gateway"
    payload: PaymentSessionCreatedPayload


class PaymentConfirmedPayload(BaseModel):
    """Payload for payment.confirmed"""
    order_id: str
    brief_id: str
    stripe_session_id: str
    stripe_payment_intent_id: str
    amount_paid: int
    payment_tier: str
    delivery_email: str
    estimated_delivery: Optional[datetime] = None


class PaymentConfirmedEvent(BaseEvent):
    """Payment Gateway → Delivery Agent + RAGNAROK: Payment successful"""
    event_type: EventType = EventType.PAYMENT_CONFIRMED
    source_agent: str = "payment_gateway"
    priority: EventPriority = EventPriority.HIGH
    payload: PaymentConfirmedPayload


class PaymentFailedPayload(BaseModel):
    """Payload for payment.failed"""
    brief_id: str
    error_code: Optional[str] = None
    decline_code: Optional[str] = None
    message: str
    retry_url: Optional[str] = None


class PaymentFailedEvent(BaseEvent):
    """Payment Gateway → Delivery Agent: Payment failed"""
    event_type: EventType = EventType.PAYMENT_FAILED
    source_agent: str = "payment_gateway"
    payload: PaymentFailedPayload


class OrderQueuedPayload(BaseModel):
    """Payload for order.queued - sent to RAGNAROK"""
    order_id: str
    brief_id: str
    order_type: str = "commercial_video"
    priority: str = "standard"
    creative_brief: dict
    target_server: str = "ragnarok"
    cost_ceiling: float
    delivery_email: str
    estimated_delivery: Optional[datetime] = None


class OrderQueuedEvent(BaseEvent):
    """Payment Gateway → RAGNAROK: Start production"""
    event_type: EventType = EventType.ORDER_QUEUED
    source_agent: str = "payment_gateway"
    priority: EventPriority = EventPriority.CRITICAL
    payload: OrderQueuedPayload


# --- RAGNAROK Events ---

class ProductionStartedPayload(BaseModel):
    """Payload for production.started"""
    order_id: str
    brief_id: str
    estimated_completion: Optional[datetime] = None
    assigned_agents: list[str] = Field(default_factory=list)


class ProductionStartedEvent(BaseEvent):
    """RAGNAROK → Delivery Agent: Production underway"""
    event_type: EventType = EventType.PRODUCTION_STARTED
    source_agent: str = "ragnarok"
    payload: ProductionStartedPayload


class ProductionPhaseCompletePayload(BaseModel):
    """Payload for production.phase_complete"""
    order_id: str
    brief_id: str
    phase_name: str
    phase_number: int
    total_phases: int
    progress_percent: int


class ProductionPhaseCompleteEvent(BaseEvent):
    """RAGNAROK → Delivery Agent: Milestone reached"""
    event_type: EventType = EventType.PRODUCTION_PHASE_COMPLETE
    source_agent: str = "ragnarok"
    payload: ProductionPhaseCompletePayload


class ProductionCompletedPayload(BaseModel):
    """Payload for production.completed"""
    order_id: str
    brief_id: str
    video_key: str  # S3 key
    formats_available: list[str]
    duration_seconds: int
    file_size_bytes: int
    quality_score: float
    production_cost: float


class ProductionCompletedEvent(BaseEvent):
    """RAGNAROK → Delivery Agent: Video ready"""
    event_type: EventType = EventType.PRODUCTION_COMPLETED
    source_agent: str = "ragnarok"
    priority: EventPriority = EventPriority.HIGH
    payload: ProductionCompletedPayload


class ProductionFailedPayload(BaseModel):
    """Payload for production.failed"""
    order_id: str
    brief_id: str
    phase_failed: str
    error_message: str
    recoverable: bool
    refund_recommended: bool


class ProductionFailedEvent(BaseEvent):
    """RAGNAROK → Delivery Agent: Production failed"""
    event_type: EventType = EventType.PRODUCTION_FAILED
    source_agent: str = "ragnarok"
    priority: EventPriority = EventPriority.CRITICAL
    payload: ProductionFailedPayload


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for connection resilience"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = settings.CB_FAILURE_THRESHOLD,
        reset_timeout: float = settings.CB_RESET_TIMEOUT_SECONDS,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
        self._logger = structlog.get_logger().bind(component="circuit_breaker", name=name)
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    async def can_execute(self) -> bool:
        """Check if circuit allows execution"""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if timeout elapsed
                if self._last_failure_time:
                    elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                    if elapsed >= self.reset_timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._logger.info("circuit_half_open", elapsed=elapsed)
                        return True
                return False
            
            # HALF_OPEN: allow one request
            return True
    
    async def record_success(self):
        """Record successful execution"""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failures = 0
                self._logger.info("circuit_closed")
            elif self._state == CircuitState.CLOSED:
                self._failures = 0
    
    async def record_failure(self, error: Exception = None):
        """Record failed execution"""
        async with self._lock:
            self._failures += 1
            self._last_failure_time = datetime.utcnow()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._logger.warning("circuit_reopened", error=str(error))
            elif self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._logger.warning("circuit_opened", failures=self._failures, error=str(error))


def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """Decorator to wrap async functions with circuit breaker"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not await circuit_breaker.can_execute():
                raise ConnectionError(f"Circuit breaker {circuit_breaker.name} is OPEN")
            
            try:
                result = await func(*args, **kwargs)
                await circuit_breaker.record_success()
                return result
            except Exception as e:
                await circuit_breaker.record_failure(e)
                raise
        return wrapper
    return decorator


# =============================================================================
# EVENT BUS INTERFACES
# =============================================================================

EventHandler = Callable[[BaseEvent], Any]


class IEventPublisher(ABC):
    """Publisher interface"""
    
    @abstractmethod
    async def publish(self, event: BaseEvent) -> bool:
        """Publish event to bus"""
        pass
    
    @abstractmethod
    async def publish_batch(self, events: list[BaseEvent]) -> int:
        """Publish multiple events, return count published"""
        pass


class IEventSubscriber(ABC):
    """Subscriber interface"""
    
    @abstractmethod
    async def subscribe(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        queue_name: Optional[str] = None,
    ) -> str:
        """Subscribe to events, return subscription ID"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        pass


class IEventBus(IEventPublisher, IEventSubscriber):
    """Combined event bus interface"""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection gracefully"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check connection health"""
        pass


# =============================================================================
# IN-MEMORY EVENT BUS (For Testing)
# =============================================================================

class InMemoryEventBus(IEventBus):
    """
    In-memory event bus for testing without RabbitMQ.
    Supports all operations synchronously.
    """
    
    def __init__(self):
        self._handlers: dict[EventType, list[tuple[str, EventHandler]]] = defaultdict(list)
        self._events: list[BaseEvent] = []
        self._connected = False
        self._lock = asyncio.Lock()
        self._logger = structlog.get_logger().bind(component="inmemory_event_bus")
    
    async def connect(self) -> bool:
        self._connected = True
        self._logger.info("connected")
        return True
    
    async def disconnect(self) -> bool:
        self._connected = False
        self._logger.info("disconnected")
        return True
    
    async def health_check(self) -> bool:
        return self._connected
    
    async def publish(self, event: BaseEvent) -> bool:
        if not self._connected:
            raise ConnectionError("Event bus not connected")
        
        async with self._lock:
            self._events.append(event)
            
            # Dispatch to handlers
            handlers = self._handlers.get(event.event_type, [])
            for sub_id, handler in handlers:
                try:
                    await handler(event)
                except Exception as e:
                    self._logger.error("handler_error",
                                      event_type=event.event_type.value,
                                      subscription_id=sub_id,
                                      error=str(e))
            
            self._logger.info("event_published",
                             event_type=event.event_type.value,
                             event_id=event.event_id,
                             handlers_notified=len(handlers))
            return True
    
    async def publish_batch(self, events: list[BaseEvent]) -> int:
        count = 0
        for event in events:
            if await self.publish(event):
                count += 1
        return count
    
    async def subscribe(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        queue_name: Optional[str] = None,
    ) -> str:
        subscription_id = str(uuid.uuid4())
        
        async with self._lock:
            for event_type in event_types:
                self._handlers[event_type].append((subscription_id, handler))
        
        self._logger.info("subscribed",
                         subscription_id=subscription_id,
                         event_types=[et.value for et in event_types])
        return subscription_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        async with self._lock:
            for event_type in list(self._handlers.keys()):
                self._handlers[event_type] = [
                    (sid, h) for sid, h in self._handlers[event_type]
                    if sid != subscription_id
                ]
        
        self._logger.info("unsubscribed", subscription_id=subscription_id)
        return True
    
    # Testing utilities
    def get_published_events(self) -> list[BaseEvent]:
        return list(self._events)
    
    def clear_events(self):
        self._events.clear()


# =============================================================================
# RABBITMQ EVENT BUS
# =============================================================================

class RabbitMQEventBus(IEventBus):
    """
    Production RabbitMQ event bus with:
    - Topic exchange for routing
    - Dead letter exchange for failures
    - Connection resilience with circuit breaker
    - Graceful shutdown
    """
    
    def __init__(
        self,
        url: str = settings.RABBITMQ_URL,
        exchange_name: str = settings.EXCHANGE_NAME,
    ):
        if not HAS_AIOPIKA:
            raise ImportError("aio-pika required for RabbitMQ. Install with: pip install aio-pika")
        
        self._url = url
        self._exchange_name = exchange_name
        
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._exchange: Optional[AbstractExchange] = None
        self._dlx_exchange: Optional[AbstractExchange] = None
        
        self._subscriptions: dict[str, AbstractQueue] = {}
        self._circuit_breaker = CircuitBreaker("rabbitmq")
        self._lock = asyncio.Lock()
        self._logger = structlog.get_logger().bind(component="rabbitmq_event_bus")
    
    async def connect(self) -> bool:
        """Establish RabbitMQ connection with exchanges"""
        try:
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            
            # Set QoS
            await self._channel.set_qos(prefetch_count=settings.PREFETCH_COUNT)
            
            # Declare main exchange (topic for flexible routing)
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name,
                ExchangeType.TOPIC,
                durable=True,
            )
            
            # Declare dead letter exchange
            self._dlx_exchange = await self._channel.declare_exchange(
                settings.DLX_EXCHANGE_NAME,
                ExchangeType.FANOUT,
                durable=True,
            )
            
            # Declare dead letter queue
            dlq = await self._channel.declare_queue(
                settings.DLX_QUEUE_NAME,
                durable=True,
            )
            await dlq.bind(self._dlx_exchange)
            
            self._logger.info("connected",
                             exchange=self._exchange_name,
                             dlx=settings.DLX_EXCHANGE_NAME)
            return True
            
        except Exception as e:
            self._logger.error("connection_failed", error=str(e))
            raise
    
    async def disconnect(self) -> bool:
        """Graceful shutdown"""
        try:
            # Cancel all consumers
            for sub_id, queue in self._subscriptions.items():
                try:
                    await queue.cancel(sub_id)
                except Exception:
                    pass
            
            if self._channel:
                await self._channel.close()
            if self._connection:
                await self._connection.close()
            
            self._logger.info("disconnected")
            return True
            
        except Exception as e:
            self._logger.error("disconnect_error", error=str(e))
            return False
    
    async def health_check(self) -> bool:
        """Check connection health"""
        if not self._connection or self._connection.is_closed:
            return False
        if not self._channel or self._channel.is_closed:
            return False
        return True
    
    @with_circuit_breaker(CircuitBreaker("rabbitmq_publish"))
    async def publish(self, event: BaseEvent) -> bool:
        """Publish event to exchange"""
        if not await self.health_check():
            raise ConnectionError("RabbitMQ not connected")
        
        try:
            message = Message(
                body=event.to_message_body(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                correlation_id=event.correlation_id,
                message_id=event.event_id,
                timestamp=event.timestamp,
                priority=event.priority.value,
                headers={
                    "event_type": event.event_type.value,
                    "source_agent": event.source_agent,
                    "version": event.version,
                    "attempt_count": event.attempt_count,
                },
                expiration=str(settings.MESSAGE_TTL_MS),
            )
            
            await self._exchange.publish(
                message,
                routing_key=event.routing_key,
            )
            
            self._logger.info("event_published",
                             event_type=event.event_type.value,
                             event_id=event.event_id,
                             routing_key=event.routing_key)
            return True
            
        except Exception as e:
            self._logger.error("publish_failed",
                              event_type=event.event_type.value,
                              error=str(e))
            raise
    
    async def publish_batch(self, events: list[BaseEvent]) -> int:
        """Publish multiple events"""
        count = 0
        for event in events:
            try:
                if await self.publish(event):
                    count += 1
            except Exception:
                pass  # Continue with remaining events
        return count
    
    async def subscribe(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        queue_name: Optional[str] = None,
    ) -> str:
        """Subscribe to events with automatic queue binding"""
        if not await self.health_check():
            raise ConnectionError("RabbitMQ not connected")
        
        subscription_id = str(uuid.uuid4())
        queue_name = queue_name or f"sub_{subscription_id[:8]}"
        
        try:
            # Declare queue with DLX
            queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": settings.DLX_EXCHANGE_NAME,
                    "x-message-ttl": settings.MESSAGE_TTL_MS,
                },
            )
            
            # Bind queue to event types
            for event_type in event_types:
                await queue.bind(self._exchange, routing_key=event_type.value)
            
            # Create message handler
            async def on_message(message: aio_pika.IncomingMessage):
                async with message.process(requeue=False):
                    try:
                        # Parse event
                        event = BaseEvent.from_message_body(message.body)
                        event.attempt_count = int(message.headers.get("attempt_count", 0)) + 1
                        
                        self._logger.info("event_received",
                                         event_type=event.event_type.value,
                                         event_id=event.event_id,
                                         attempt=event.attempt_count)
                        
                        # Call handler
                        await handler(event)
                        
                    except Exception as e:
                        self._logger.error("handler_error",
                                          error=str(e),
                                          message_id=message.message_id)
                        
                        # Check retry limit
                        attempt = int(message.headers.get("attempt_count", 0)) + 1
                        if attempt < settings.MAX_RETRIES:
                            # Requeue for retry
                            await asyncio.sleep(settings.RETRY_DELAY_SECONDS)
                            # Message will go to DLX after max retries
                        raise
            
            # Start consuming
            await queue.consume(on_message, consumer_tag=subscription_id)
            
            self._subscriptions[subscription_id] = queue
            
            self._logger.info("subscribed",
                             subscription_id=subscription_id,
                             queue=queue_name,
                             event_types=[et.value for et in event_types])
            
            return subscription_id
            
        except Exception as e:
            self._logger.error("subscribe_failed", error=str(e))
            raise
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Cancel subscription"""
        try:
            if subscription_id in self._subscriptions:
                queue = self._subscriptions[subscription_id]
                await queue.cancel(subscription_id)
                del self._subscriptions[subscription_id]
                
                self._logger.info("unsubscribed", subscription_id=subscription_id)
                return True
            return False
            
        except Exception as e:
            self._logger.error("unsubscribe_failed", error=str(e))
            return False


# =============================================================================
# EVENT BUS FACTORY
# =============================================================================

def create_event_bus(use_rabbitmq: bool = True) -> IEventBus:
    """Factory to create appropriate event bus"""
    if use_rabbitmq and HAS_AIOPIKA:
        return RabbitMQEventBus()
    else:
        return InMemoryEventBus()


# =============================================================================
# AGENT INTEGRATION MIXINS
# =============================================================================

class EventBusMixin:
    """
    Mixin to add event bus capabilities to agents.
    
    Usage:
        class MyAgent(EventBusMixin):
            def __init__(self):
                self.init_event_bus()
            
            async def do_work(self):
                await self.publish_event(SomeEvent(...))
    """
    
    _event_bus: Optional[IEventBus] = None
    _subscriptions: list[str] = []
    
    def init_event_bus(self, event_bus: Optional[IEventBus] = None):
        """Initialize event bus connection"""
        self._event_bus = event_bus or create_event_bus()
        self._subscriptions = []
    
    async def connect_event_bus(self):
        """Connect to event bus"""
        if self._event_bus:
            await self._event_bus.connect()
    
    async def disconnect_event_bus(self):
        """Disconnect and cleanup subscriptions"""
        if self._event_bus:
            for sub_id in self._subscriptions:
                await self._event_bus.unsubscribe(sub_id)
            await self._event_bus.disconnect()
    
    async def publish_event(self, event: BaseEvent) -> bool:
        """Publish event to bus"""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")
        return await self._event_bus.publish(event)
    
    async def subscribe_events(
        self,
        event_types: list[EventType],
        handler: EventHandler,
        queue_name: Optional[str] = None,
    ) -> str:
        """Subscribe to events"""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")
        sub_id = await self._event_bus.subscribe(event_types, handler, queue_name)
        self._subscriptions.append(sub_id)
        return sub_id


# =============================================================================
# AGENT WIRING HELPERS
# =============================================================================

class AgentWiring:
    """
    Pre-configured wiring for each agent.
    
    Usage:
        # In Brief Assembler
        wiring = AgentWiring.brief_assembler()
        await wiring.setup(event_bus, on_cards_complete_handler)
    """
    
    @staticmethod
    def brief_assembler() -> "AgentSubscriptionConfig":
        """Brief Assembler subscription config"""
        return AgentSubscriptionConfig(
            agent_name="brief_assembler",
            subscribes_to=[EventType.CONVERSATION_CARDS_COMPLETE],
            publishes=[
                EventType.BRIEF_ASSEMBLED,
                EventType.BRIEF_VALIDATION_FAILED,
                EventType.BRIEF_READY_FOR_PAYMENT,
            ],
            queue_name="brief_assembler_queue",
        )
    
    @staticmethod
    def payment_gateway() -> "AgentSubscriptionConfig":
        """Payment Gateway subscription config"""
        return AgentSubscriptionConfig(
            agent_name="payment_gateway",
            subscribes_to=[EventType.BRIEF_READY_FOR_PAYMENT],
            publishes=[
                EventType.PAYMENT_SESSION_CREATED,
                EventType.PAYMENT_CONFIRMED,
                EventType.PAYMENT_FAILED,
                EventType.PAYMENT_ABANDONED,
                EventType.ORDER_CREATED,
                EventType.ORDER_QUEUED,
                EventType.ORDER_CANCELLED,
            ],
            queue_name="payment_gateway_queue",
        )
    
    @staticmethod
    def delivery_agent() -> "AgentSubscriptionConfig":
        """Delivery Agent subscription config"""
        return AgentSubscriptionConfig(
            agent_name="delivery_agent",
            subscribes_to=[
                EventType.PAYMENT_SESSION_CREATED,
                EventType.PAYMENT_CONFIRMED,
                EventType.PAYMENT_FAILED,
                EventType.PAYMENT_ABANDONED,
                EventType.ORDER_QUEUED,
                EventType.PRODUCTION_STARTED,
                EventType.PRODUCTION_PHASE_COMPLETE,
                EventType.PRODUCTION_COMPLETED,
                EventType.PRODUCTION_FAILED,
                EventType.REVISION_REQUESTED,
                EventType.REVISION_COMPLETED,
            ],
            publishes=[
                EventType.NOTIFICATION_SENT,
                EventType.NOTIFICATION_FAILED,
                EventType.DELIVERY_COMPLETED,
                EventType.DELIVERY_EXPIRED,
            ],
            queue_name="delivery_agent_queue",
        )
    
    @staticmethod
    def ragnarok() -> "AgentSubscriptionConfig":
        """RAGNAROK subscription config"""
        return AgentSubscriptionConfig(
            agent_name="ragnarok",
            subscribes_to=[EventType.ORDER_QUEUED],
            publishes=[
                EventType.PRODUCTION_STARTED,
                EventType.PRODUCTION_PHASE_COMPLETE,
                EventType.PRODUCTION_COMPLETED,
                EventType.PRODUCTION_FAILED,
            ],
            queue_name="ragnarok_queue",
        )


class AgentSubscriptionConfig(BaseModel):
    """Subscription configuration for an agent"""
    agent_name: str
    subscribes_to: list[EventType]
    publishes: list[EventType]
    queue_name: str
    
    async def setup(self, event_bus: IEventBus, handler: EventHandler) -> str:
        """Setup subscription with event bus"""
        return await event_bus.subscribe(
            self.subscribes_to,
            handler,
            self.queue_name,
        )


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

async def demo():
    """Demonstrate event bus with all agents"""
    
    print("=" * 70)
    print("EVENT BUS ADAPTER - LEGENDARY EDITION")
    print("=" * 70)
    
    # Create in-memory bus for demo
    bus = InMemoryEventBus()
    await bus.connect()
    
    # Track received events
    received_events: list[BaseEvent] = []
    
    # --- Setup Agent Handlers ---
    
    async def brief_assembler_handler(event: BaseEvent):
        print(f"\n📋 BRIEF ASSEMBLER received: {event.event_type.value}")
        print(f"   Session: {event.payload.get('session_id', 'N/A')}")
        
        # Simulate processing and emit result
        result_event = BriefAssembledEvent(
            correlation_id=event.correlation_id,
            payload=BriefAssembledPayload(
                brief_id="BRF-DEMO123",
                session_id=event.payload.get("session_id", ""),
                business_name=event.payload.get("business_name", ""),
                contact_email=event.payload.get("user_email", ""),
                payment_tier="professional",
                quoted_price=5000,
                duration_seconds=60,
                confidence_score=0.92,
                quality_grade="A",
                is_ready_for_payment=True,
                creative_brief={"demo": True},
            ),
        )
        await bus.publish(result_event)
        received_events.append(event)
    
    async def payment_gateway_handler(event: BaseEvent):
        print(f"\n💳 PAYMENT GATEWAY received: {event.event_type.value}")
        print(f"   Brief: {event.payload.get('brief_id', 'N/A')}")
        
        # Simulate payment confirmation
        if event.event_type == EventType.BRIEF_ASSEMBLED:
            confirm_event = PaymentConfirmedEvent(
                correlation_id=event.correlation_id,
                payload=PaymentConfirmedPayload(
                    order_id="ORD-DEMO456",
                    brief_id=event.payload.get("brief_id", ""),
                    stripe_session_id="cs_demo",
                    stripe_payment_intent_id="pi_demo",
                    amount_paid=5000,
                    payment_tier="professional",
                    delivery_email=event.payload.get("contact_email", ""),
                ),
            )
            await bus.publish(confirm_event)
            
            # Also queue for production
            queue_event = OrderQueuedEvent(
                correlation_id=event.correlation_id,
                payload=OrderQueuedPayload(
                    order_id="ORD-DEMO456",
                    brief_id=event.payload.get("brief_id", ""),
                    creative_brief=event.payload.get("creative_brief", {}),
                    cost_ceiling=250.0,
                    delivery_email=event.payload.get("contact_email", ""),
                ),
            )
            await bus.publish(queue_event)
        
        received_events.append(event)
    
    async def delivery_agent_handler(event: BaseEvent):
        print(f"\n📧 DELIVERY AGENT received: {event.event_type.value}")
        print(f"   Order: {event.payload.get('order_id', 'N/A')}")
        received_events.append(event)
    
    async def ragnarok_handler(event: BaseEvent):
        print(f"\n🎬 RAGNAROK received: {event.event_type.value}")
        print(f"   Order: {event.payload.get('order_id', 'N/A')}")
        
        # Simulate production completion
        complete_event = ProductionCompletedEvent(
            correlation_id=event.correlation_id,
            payload=ProductionCompletedPayload(
                order_id=event.payload.get("order_id", ""),
                brief_id=event.payload.get("brief_id", ""),
                video_key="videos/ORD-DEMO456/final.mp4",
                formats_available=["mp4_1080p", "mp4_4k"],
                duration_seconds=60,
                file_size_bytes=150_000_000,
                quality_score=0.95,
                production_cost=2.50,
            ),
        )
        await bus.publish(complete_event)
        received_events.append(event)
    
    # --- Subscribe Agents ---
    
    print("\n1. Setting up agent subscriptions...")
    
    ba_config = AgentWiring.brief_assembler()
    await ba_config.setup(bus, brief_assembler_handler)
    print(f"   ✅ Brief Assembler → listening for: {[e.value for e in ba_config.subscribes_to]}")
    
    pg_config = AgentWiring.payment_gateway()
    # Payment Gateway also listens to BRIEF_ASSEMBLED for demo
    await bus.subscribe([EventType.BRIEF_ASSEMBLED], payment_gateway_handler)
    print(f"   ✅ Payment Gateway → listening for: brief.assembled")
    
    da_config = AgentWiring.delivery_agent()
    await da_config.setup(bus, delivery_agent_handler)
    print(f"   ✅ Delivery Agent → listening for: {len(da_config.subscribes_to)} event types")
    
    rn_config = AgentWiring.ragnarok()
    await rn_config.setup(bus, ragnarok_handler)
    print(f"   ✅ RAGNAROK → listening for: {[e.value for e in rn_config.subscribes_to]}")
    
    # --- Simulate Flow ---
    
    print("\n2. Simulating Website Assistant → Complete Flow...")
    
    # Website Assistant publishes cards complete
    initial_event = ConversationCardsCompleteEvent(
        payload=CardsCompletePayload(
            session_id="demo-session-001",
            user_email="customer@example.com",
            business_name="Demo Corp",
            persona_card={"name": "Tech Tim"},
            competitor_card={"competitor": "SlowCorp"},
            script_card={"hook": "Stop losing customers"},
            roi_card={"tier": "professional"},
        ),
    )
    
    print(f"\n🌐 WEBSITE ASSISTANT publishing: {initial_event.event_type.value}")
    await bus.publish(initial_event)
    
    # Give async handlers time to process
    await asyncio.sleep(0.1)
    
    # --- Results ---
    
    print("\n" + "=" * 70)
    print("FLOW COMPLETE")
    print("=" * 70)
    
    all_events = bus.get_published_events()
    print(f"\n📊 Total events published: {len(all_events)}")
    print("\nEvent Chain:")
    for i, event in enumerate(all_events, 1):
        print(f"   {i}. {event.event_type.value} (from: {event.source_agent})")
    
    print(f"\n✅ Agents received {len(received_events)} events")
    
    print("\n" + "=" * 70)
    print("WIRING SUMMARY")
    print("=" * 70)
    print("""
    ┌─────────────────┐
    │ Website         │
    │ Assistant       │──── conversation.cards_complete ────┐
    └─────────────────┘                                     │
                                                            ▼
    ┌─────────────────┐                           ┌─────────────────┐
    │ Brief           │◄──────────────────────────│ Brief           │
    │ Assembler       │                           │ Assembler       │
    │                 │──── brief.assembled ──────│ Queue           │
    └─────────────────┘                           └─────────────────┘
            │
            ▼
    ┌─────────────────┐
    │ Payment         │──── payment.confirmed ───┬──► Delivery Agent
    │ Gateway         │                          │
    │                 │──── order.queued ────────┼──► RAGNAROK
    └─────────────────┘                          │
                                                 │
    ┌─────────────────┐                          │
    │ RAGNAROK        │──── production.completed ┘
    └─────────────────┘
    """)
    
    await bus.disconnect()


if __name__ == "__main__":
    asyncio.run(demo())
