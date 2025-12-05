"""
Agent 3: Delivery Agent (Courier Chris) - LEGENDARY EDITION
===========================================================
Secure Enterprise Asset Delivery System with:
- Just-in-Time (JIT) Downloads (no long-lived S3 links in emails)
- Secure Token Exchange (JWT-style tokens with usage limits)
- SendGrid Webhook Tracking (bounce/drop/open detection)
- Download Audit Trail (IP, User-Agent, timestamp logging)
- CloudFront CDN Integration (signed URLs with custom policy)
- Smart Template Routing (tier-based branding)

pip install pydantic boto3 sendgrid structlog pyjwt cryptography
"""

import asyncio
import hashlib
import hmac
import json
import secrets
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Any, Callable
from urllib.parse import urlencode
import base64

from pydantic import BaseModel, Field, computed_field, field_validator
import boto3
from botocore.config import Config
import structlog

# Optional: For CloudFront signed URLs
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# Optional: For JWT tokens
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False


# =============================================================================
# STRUCTURED LOGGING SETUP
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
    wrapper_class=structlog.make_filtering_bound_logger(structlog.logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

class Settings:
    # SendGrid
    SENDGRID_API_KEY: str = "SG.YOUR_KEY"
    SENDGRID_FROM_EMAIL: str = "delivery@videoforge.ai"
    SENDGRID_WEBHOOK_SECRET: str = "your-webhook-signing-secret"
    
    # AWS S3
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "videoforge-deliveries"
    
    # CloudFront (CDN)
    CLOUDFRONT_ENABLED: bool = True
    CLOUDFRONT_DOMAIN: str = "d123456789.cloudfront.net"
    CLOUDFRONT_KEY_PAIR_ID: str = "KXXXXXXXXXX"
    CLOUDFRONT_PRIVATE_KEY_PATH: str = "/secrets/cloudfront-private-key.pem"
    
    # Security
    PORTAL_URL: str = "https://portal.videoforge.ai"
    TOKEN_SECRET: str = "your-256-bit-secret-key-here"
    
    # Token expiry
    PORTAL_TOKEN_EXPIRY_HOURS: int = 168  # 7 days (token in email)
    DOWNLOAD_LINK_EXPIRY_MINUTES: int = 15  # JIT link (after token exchange)
    SINGLE_USE_TOKEN_EXPIRY_MINUTES: int = 60  # Enterprise single-use
    
    # Limits
    MAX_DOWNLOADS_PER_TOKEN: int = 10  # Prevent abuse
    ENTERPRISE_MAX_DOWNLOADS: int = 50
    
    # Alert thresholds
    BOUNCE_ALERT_THRESHOLD: int = 3  # Alert after 3 bounces for same email


settings = Settings()


# =============================================================================
# ENUMS
# =============================================================================

class NotificationType(str, Enum):
    PAYMENT_CONFIRMED = "payment_confirmed"
    PRODUCTION_STARTED = "production_started"
    MILESTONE_UPDATE = "milestone_update"
    DELIVERY_FINAL = "delivery_final"
    PAYMENT_FAILED = "payment_failed"
    CART_RECOVERY = "cart_recovery"
    CART_FINAL_REMINDER = "cart_final_reminder"
    DELIVERY_REMINDER = "delivery_reminder"
    DOWNLOAD_EXPIRING = "download_expiring"


class DeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    DROPPED = "dropped"
    FAILED = "failed"
    EXPIRED = "expired"


class TokenStatus(str, Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"
    EXHAUSTED = "exhausted"  # Max downloads reached


class PaymentTier(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class AuditEventType(str, Enum):
    TOKEN_CREATED = "token.created"
    TOKEN_EXCHANGED = "token.exchanged"
    TOKEN_EXPIRED = "token.expired"
    TOKEN_REVOKED = "token.revoked"
    DOWNLOAD_STARTED = "download.started"
    DOWNLOAD_COMPLETED = "download.completed"
    DOWNLOAD_FAILED = "download.failed"
    EMAIL_SENT = "email.sent"
    EMAIL_DELIVERED = "email.delivered"
    EMAIL_OPENED = "email.opened"
    EMAIL_CLICKED = "email.clicked"
    EMAIL_BOUNCED = "email.bounced"
    EMAIL_DROPPED = "email.dropped"
    ALERT_TRIGGERED = "alert.triggered"


# =============================================================================
# DOMAIN MODELS
# =============================================================================

class ProductionOrder(BaseModel):
    """Input from Agent 2"""
    order_id: str
    brief_id: str
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    delivery_email: str
    payment_tier: PaymentTier
    amount_paid: int
    estimated_delivery: Optional[datetime] = None
    business_name: str = "Customer"
    metadata: dict = Field(default_factory=dict)


class DeliveryToken(BaseModel):
    """Secure download token (replaces direct S3 links)"""
    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_hash: str  # Stored hash, not raw token
    order_id: str
    correlation_id: str
    
    status: TokenStatus = TokenStatus.ACTIVE
    payment_tier: PaymentTier
    
    # Security
    max_downloads: int = settings.MAX_DOWNLOADS_PER_TOKEN
    download_count: int = 0
    allowed_ip_cidrs: list[str] = Field(default_factory=list)  # Optional IP restriction
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    last_used_at: Optional[datetime] = None
    
    # Asset info
    video_key: str  # S3 key
    formats_available: list[str] = Field(default_factory=lambda: ["mp4_1080p"])
    
    @computed_field
    @property
    def is_valid(self) -> bool:
        if self.status != TokenStatus.ACTIVE:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        if self.download_count >= self.max_downloads:
            return False
        return True
    
    @computed_field
    @property
    def remaining_downloads(self) -> int:
        return max(0, self.max_downloads - self.download_count)
    
    def record_download(self) -> "DeliveryToken":
        """Immutable download recording"""
        new_count = self.download_count + 1
        new_status = TokenStatus.EXHAUSTED if new_count >= self.max_downloads else self.status
        return self.model_copy(update={
            "download_count": new_count,
            "last_used_at": datetime.utcnow(),
            "status": new_status,
        })


class DownloadAttempt(BaseModel):
    """Audit record for download attempts"""
    attempt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_id: str
    order_id: str
    correlation_id: str
    
    # Request info
    ip_address: str
    user_agent: str
    referer: Optional[str] = None
    
    # Result
    success: bool
    failure_reason: Optional[str] = None
    presigned_url_generated: bool = False
    
    # Timing
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    download_duration_ms: Optional[int] = None


class NotificationRecord(BaseModel):
    """Email notification tracking"""
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    correlation_id: str
    
    notification_type: NotificationType
    recipient_email: str
    payment_tier: PaymentTier
    
    # SendGrid tracking
    sendgrid_message_id: Optional[str] = None
    template_id: str
    
    # Status
    status: DeliveryStatus = DeliveryStatus.PENDING
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    
    # Retry
    attempt_count: int = 1
    last_error: Optional[str] = None


class DeliveryAlert(BaseModel):
    """Alert for delivery issues"""
    alert_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_type: str  # "bounce", "drop", "fraud_attempt"
    severity: str  # "low", "medium", "high", "critical"
    order_id: str
    correlation_id: str
    recipient_email: str
    message: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False


class SendGridWebhookEvent(BaseModel):
    """Parsed SendGrid webhook event"""
    event_type: str  # delivered, open, click, bounce, dropped, etc.
    email: str
    timestamp: datetime
    sg_message_id: str
    reason: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    url: Optional[str] = None
    raw_payload: dict = Field(default_factory=dict)


# =============================================================================
# PERSISTENCE INTERFACES
# =============================================================================

class ITokenRepository(ABC):
    """Token storage interface"""
    
    @abstractmethod
    async def save(self, token: DeliveryToken) -> DeliveryToken:
        pass
    
    @abstractmethod
    async def get_by_hash(self, token_hash: str) -> Optional[DeliveryToken]:
        pass
    
    @abstractmethod
    async def get_by_order(self, order_id: str) -> list[DeliveryToken]:
        pass
    
    @abstractmethod
    async def update(self, token: DeliveryToken) -> DeliveryToken:
        pass
    
    @abstractmethod
    async def revoke(self, token_id: str) -> bool:
        pass


class INotificationRepository(ABC):
    """Notification tracking interface"""
    
    @abstractmethod
    async def save(self, record: NotificationRecord) -> NotificationRecord:
        pass
    
    @abstractmethod
    async def get_by_message_id(self, message_id: str) -> Optional[NotificationRecord]:
        pass
    
    @abstractmethod
    async def update_status(self, message_id: str, status: DeliveryStatus, **kwargs) -> bool:
        pass
    
    @abstractmethod
    async def get_bounces_for_email(self, email: str, since: datetime) -> list[NotificationRecord]:
        pass


class IDownloadAuditLog(ABC):
    """Download audit interface"""
    
    @abstractmethod
    async def log_attempt(self, attempt: DownloadAttempt) -> None:
        pass
    
    @abstractmethod
    async def get_attempts_for_token(self, token_id: str) -> list[DownloadAttempt]:
        pass
    
    @abstractmethod
    async def get_attempts_for_order(self, order_id: str) -> list[DownloadAttempt]:
        pass


class IAlertService(ABC):
    """Alert/notification service interface"""
    
    @abstractmethod
    async def send_alert(self, alert: DeliveryAlert) -> None:
        pass
    
    @abstractmethod
    async def get_unacknowledged(self) -> list[DeliveryAlert]:
        pass


# =============================================================================
# IN-MEMORY IMPLEMENTATIONS
# =============================================================================

class InMemoryTokenRepository(ITokenRepository):
    """Thread-safe token storage"""
    
    def __init__(self):
        self._tokens: dict[str, DeliveryToken] = {}  # token_hash -> token
        self._by_order: dict[str, list[str]] = defaultdict(list)  # order_id -> [token_hashes]
        self._lock = asyncio.Lock()
    
    async def save(self, token: DeliveryToken) -> DeliveryToken:
        async with self._lock:
            self._tokens[token.token_hash] = token
            self._by_order[token.order_id].append(token.token_hash)
            return token
    
    async def get_by_hash(self, token_hash: str) -> Optional[DeliveryToken]:
        async with self._lock:
            return self._tokens.get(token_hash)
    
    async def get_by_order(self, order_id: str) -> list[DeliveryToken]:
        async with self._lock:
            hashes = self._by_order.get(order_id, [])
            return [self._tokens[h] for h in hashes if h in self._tokens]
    
    async def update(self, token: DeliveryToken) -> DeliveryToken:
        async with self._lock:
            self._tokens[token.token_hash] = token
            return token
    
    async def revoke(self, token_id: str) -> bool:
        async with self._lock:
            for token in self._tokens.values():
                if token.token_id == token_id:
                    token.status = TokenStatus.REVOKED
                    return True
            return False


class InMemoryNotificationRepository(INotificationRepository):
    """Notification tracking"""
    
    def __init__(self):
        self._records: dict[str, NotificationRecord] = {}  # message_id -> record
        self._lock = asyncio.Lock()
    
    async def save(self, record: NotificationRecord) -> NotificationRecord:
        async with self._lock:
            if record.sendgrid_message_id:
                self._records[record.sendgrid_message_id] = record
            self._records[record.notification_id] = record
            return record
    
    async def get_by_message_id(self, message_id: str) -> Optional[NotificationRecord]:
        async with self._lock:
            return self._records.get(message_id)
    
    async def update_status(self, message_id: str, status: DeliveryStatus, **kwargs) -> bool:
        async with self._lock:
            record = self._records.get(message_id)
            if record:
                record.status = status
                for key, value in kwargs.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                return True
            return False
    
    async def get_bounces_for_email(self, email: str, since: datetime) -> list[NotificationRecord]:
        async with self._lock:
            return [
                r for r in self._records.values()
                if r.recipient_email == email
                and r.status == DeliveryStatus.BOUNCED
                and r.bounced_at and r.bounced_at >= since
            ]


class InMemoryDownloadAuditLog(IDownloadAuditLog):
    """Download audit logging"""
    
    def __init__(self):
        self._attempts: list[DownloadAttempt] = []
        self._lock = asyncio.Lock()
    
    async def log_attempt(self, attempt: DownloadAttempt) -> None:
        async with self._lock:
            self._attempts.append(attempt)
    
    async def get_attempts_for_token(self, token_id: str) -> list[DownloadAttempt]:
        async with self._lock:
            return [a for a in self._attempts if a.token_id == token_id]
    
    async def get_attempts_for_order(self, order_id: str) -> list[DownloadAttempt]:
        async with self._lock:
            return [a for a in self._attempts if a.order_id == order_id]


class InMemoryAlertService(IAlertService):
    """Alert service"""
    
    def __init__(self):
        self._alerts: list[DeliveryAlert] = []
        self._lock = asyncio.Lock()
    
    async def send_alert(self, alert: DeliveryAlert) -> None:
        async with self._lock:
            self._alerts.append(alert)
            # In production: send to Slack, PagerDuty, etc.
    
    async def get_unacknowledged(self) -> list[DeliveryAlert]:
        async with self._lock:
            return [a for a in self._alerts if not a.acknowledged]


# =============================================================================
# URL GENERATORS (S3 and CloudFront)
# =============================================================================

class IUrlGenerator(ABC):
    """URL generator interface for swapping S3/CloudFront"""
    
    @abstractmethod
    async def generate_download_url(
        self,
        key: str,
        filename: str,
        expires_in_seconds: int,
    ) -> str:
        pass


class S3UrlGenerator(IUrlGenerator):
    """Direct S3 presigned URL generator"""
    
    def __init__(self, bucket: str = settings.S3_BUCKET, region: str = settings.AWS_REGION):
        self.bucket = bucket
        self.s3 = boto3.client(
            "s3",
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
    
    async def generate_download_url(
        self,
        key: str,
        filename: str,
        expires_in_seconds: int,
    ) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=expires_in_seconds,
        )


class CloudFrontUrlGenerator(IUrlGenerator):
    """CloudFront signed URL generator (more secure, faster)"""
    
    def __init__(
        self,
        domain: str = settings.CLOUDFRONT_DOMAIN,
        key_pair_id: str = settings.CLOUDFRONT_KEY_PAIR_ID,
        private_key_path: str = settings.CLOUDFRONT_PRIVATE_KEY_PATH,
    ):
        self.domain = domain
        self.key_pair_id = key_pair_id
        self._private_key = None
        self._private_key_path = private_key_path
    
    def _load_private_key(self):
        """Load private key (lazy loading)"""
        if self._private_key is None and HAS_CRYPTO:
            try:
                with open(self._private_key_path, "rb") as f:
                    self._private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None,
                        backend=default_backend(),
                    )
            except FileNotFoundError:
                pass
        return self._private_key
    
    def _rsa_sign(self, message: bytes) -> bytes:
        """Sign message with RSA private key"""
        key = self._load_private_key()
        if key is None:
            raise RuntimeError("CloudFront private key not available")
        return key.sign(message, padding.PKCS1v15(), hashes.SHA1())
    
    async def generate_download_url(
        self,
        key: str,
        filename: str,
        expires_in_seconds: int,
    ) -> str:
        """Generate CloudFront signed URL with custom policy"""
        
        # If no crypto available, fall back to mock URL
        if not HAS_CRYPTO or not self._load_private_key():
            expiry = int((datetime.utcnow() + timedelta(seconds=expires_in_seconds)).timestamp())
            return f"https://{self.domain}/{key}?Expires={expiry}&mock=true"
        
        url = f"https://{self.domain}/{key}"
        expires = int((datetime.utcnow() + timedelta(seconds=expires_in_seconds)).timestamp())
        
        # Create custom policy (allows more control than canned policy)
        policy = {
            "Statement": [{
                "Resource": url,
                "Condition": {
                    "DateLessThan": {"AWS:EpochTime": expires}
                }
            }]
        }
        
        policy_json = json.dumps(policy, separators=(",", ":"))
        policy_b64 = base64.b64encode(policy_json.encode()).decode()
        # URL-safe base64
        policy_b64 = policy_b64.replace("+", "-").replace("=", "_").replace("/", "~")
        
        # Sign policy
        signature = self._rsa_sign(policy_json.encode())
        signature_b64 = base64.b64encode(signature).decode()
        signature_b64 = signature_b64.replace("+", "-").replace("=", "_").replace("/", "~")
        
        # Build signed URL
        params = {
            "Policy": policy_b64,
            "Signature": signature_b64,
            "Key-Pair-Id": self.key_pair_id,
        }
        
        return f"{url}?{urlencode(params)}"


# =============================================================================
# TEMPLATE MANAGER (Smart Routing)
# =============================================================================

class TemplateManager:
    """
    Smart template routing based on payment tier.
    Enterprise gets "White Glove" branding, Starter gets standard.
    """
    
    # Base templates (Starter tier)
    BASE_TEMPLATES = {
        NotificationType.PAYMENT_CONFIRMED: "d-payment-confirmed-base",
        NotificationType.PRODUCTION_STARTED: "d-production-started-base",
        NotificationType.MILESTONE_UPDATE: "d-milestone-update-base",
        NotificationType.DELIVERY_FINAL: "d-delivery-final-base",
        NotificationType.PAYMENT_FAILED: "d-payment-failed-base",
        NotificationType.CART_RECOVERY: "d-cart-recovery-base",
        NotificationType.DELIVERY_REMINDER: "d-delivery-reminder-base",
        NotificationType.DOWNLOAD_EXPIRING: "d-download-expiring-base",
    }
    
    # Professional tier overrides
    PROFESSIONAL_TEMPLATES = {
        NotificationType.DELIVERY_FINAL: "d-delivery-final-professional",
    }
    
    # Enterprise tier overrides (White Glove)
    ENTERPRISE_TEMPLATES = {
        NotificationType.PAYMENT_CONFIRMED: "d-payment-confirmed-enterprise",
        NotificationType.PRODUCTION_STARTED: "d-production-started-enterprise",
        NotificationType.MILESTONE_UPDATE: "d-milestone-enterprise",
        NotificationType.DELIVERY_FINAL: "d-delivery-final-enterprise",
    }
    
    # Branding per tier
    BRANDING = {
        PaymentTier.STARTER: {
            "company_name": "VideoForge",
            "support_email": "support@videoforge.ai",
            "logo_url": "https://cdn.videoforge.ai/logo-standard.png",
            "primary_color": "#4F46E5",
            "footer_text": "Thank you for choosing VideoForge!",
        },
        PaymentTier.PROFESSIONAL: {
            "company_name": "VideoForge Pro",
            "support_email": "pro-support@videoforge.ai",
            "logo_url": "https://cdn.videoforge.ai/logo-pro.png",
            "primary_color": "#7C3AED",
            "footer_text": "Your success is our priority.",
        },
        PaymentTier.ENTERPRISE: {
            "company_name": "VideoForge Enterprise",
            "support_email": "enterprise@videoforge.ai",
            "support_phone": "+1-800-VIDEO-FORGE",
            "logo_url": "https://cdn.videoforge.ai/logo-enterprise.png",
            "primary_color": "#1E40AF",
            "footer_text": "White Glove Service • Priority Support • Dedicated Team",
            "account_manager": "Your dedicated account manager will reach out shortly.",
        },
    }
    
    def get_template_id(self, notification_type: NotificationType, tier: PaymentTier) -> str:
        """Get template ID based on tier"""
        if tier == PaymentTier.ENTERPRISE and notification_type in self.ENTERPRISE_TEMPLATES:
            return self.ENTERPRISE_TEMPLATES[notification_type]
        if tier == PaymentTier.PROFESSIONAL and notification_type in self.PROFESSIONAL_TEMPLATES:
            return self.PROFESSIONAL_TEMPLATES[notification_type]
        return self.BASE_TEMPLATES.get(notification_type, "d-generic-notification")
    
    def get_branding(self, tier: PaymentTier) -> dict:
        """Get branding variables for tier"""
        return self.BRANDING.get(tier, self.BRANDING[PaymentTier.STARTER])
    
    def build_template_data(
        self,
        notification_type: NotificationType,
        tier: PaymentTier,
        custom_data: dict,
    ) -> dict:
        """Build complete template data with branding"""
        branding = self.get_branding(tier)
        return {
            **branding,
            **custom_data,
            "notification_type": notification_type.value,
            "tier": tier.value,
            "year": datetime.utcnow().year,
        }


# =============================================================================
# DELIVERY AGENT - LEGENDARY EDITION
# =============================================================================

class DeliveryAgent:
    """
    Legendary Delivery Agent: Secure Enterprise Asset Delivery
    
    Features:
    - Just-in-Time Downloads: Portal tokens instead of direct S3 links
    - Secure Token Exchange: Hash-based tokens with usage limits
    - SendGrid Webhooks: Bounce/drop detection with alerting
    - Download Audit Trail: IP, User-Agent, timestamp logging
    - CloudFront CDN: Signed URLs for faster, more secure delivery
    - Smart Templates: Tier-based branding (Enterprise = White Glove)
    
    Flow:
    1. on_production_completed() → Creates portal token, sends email with portal link
    2. User clicks link → Frontend calls exchange_token_for_download(token)
    3. exchange_token_for_download() → Validates, generates 15-min S3/CloudFront URL
    4. User downloads → Audit logged with IP, User-Agent
    
    Example:
        agent = DeliveryAgent()
        await agent.on_production_completed(order, "videos/ORD-123.mp4")
        # Email contains: https://portal.videoforge.ai/download?token=xxx
        
        # When user clicks:
        result = await agent.exchange_token_for_download(
            token="xxx",
            ip_address="1.2.3.4",
            user_agent="Mozilla/5.0..."
        )
        # Returns short-lived download URL
    """
    
    def __init__(
        self,
        token_repo: Optional[ITokenRepository] = None,
        notification_repo: Optional[INotificationRepository] = None,
        download_audit: Optional[IDownloadAuditLog] = None,
        alert_service: Optional[IAlertService] = None,
        url_generator: Optional[IUrlGenerator] = None,
        template_manager: Optional[TemplateManager] = None,
    ):
        # Dependencies
        self.tokens = token_repo or InMemoryTokenRepository()
        self.notifications = notification_repo or InMemoryNotificationRepository()
        self.audit = download_audit or InMemoryDownloadAuditLog()
        self.alerts = alert_service or InMemoryAlertService()
        self.templates = template_manager or TemplateManager()
        
        # URL generator (CloudFront or S3)
        if url_generator:
            self.url_generator = url_generator
        elif settings.CLOUDFRONT_ENABLED:
            self.url_generator = CloudFrontUrlGenerator()
        else:
            self.url_generator = S3UrlGenerator()
        
        # Logger
        self._base_logger = structlog.get_logger()
        
        # Token secret for hashing
        self._token_secret = settings.TOKEN_SECRET.encode()
    
    def _get_logger(self, correlation_id: str = None):
        return self._base_logger.bind(
            agent="delivery_agent",
            version="2.0-legendary",
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
    
    def _generate_token(self) -> tuple[str, str]:
        """Generate raw token and its hash"""
        raw_token = secrets.token_urlsafe(32)
        token_hash = hmac.new(
            self._token_secret,
            raw_token.encode(),
            hashlib.sha256
        ).hexdigest()
        return raw_token, token_hash
    
    def _hash_token(self, raw_token: str) -> str:
        """Hash a raw token for lookup"""
        return hmac.new(
            self._token_secret,
            raw_token.encode(),
            hashlib.sha256
        ).hexdigest()
    
    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================
    
    async def on_payment_confirmed(self, order: ProductionOrder) -> NotificationRecord:
        """Send payment confirmation email"""
        log = self._get_logger(order.correlation_id)
        log.info("sending_payment_confirmation", order_id=order.order_id)
        
        return await self._send_notification(
            order=order,
            notification_type=NotificationType.PAYMENT_CONFIRMED,
            template_data={
                "order_id": order.order_id,
                "amount_paid": f"${order.amount_paid:,}",
                "payment_tier": order.payment_tier.value.title(),
                "estimated_delivery": (
                    order.estimated_delivery.strftime("%B %d, %Y")
                    if order.estimated_delivery else "5-7 business days"
                ),
                "business_name": order.business_name,
            },
        )
    
    async def on_payment_failed(
        self,
        order: ProductionOrder,
        error_message: str,
        retry_url: str,
    ) -> NotificationRecord:
        """Send payment failure email"""
        log = self._get_logger(order.correlation_id)
        log.warning("sending_payment_failure", order_id=order.order_id, error=error_message)
        
        return await self._send_notification(
            order=order,
            notification_type=NotificationType.PAYMENT_FAILED,
            template_data={
                "order_id": order.order_id,
                "error_message": error_message,
                "retry_url": retry_url,
            },
        )
    
    async def on_cart_abandoned(
        self,
        order: ProductionOrder,
        recovery_url: str,
    ) -> NotificationRecord:
        """Send cart recovery email"""
        log = self._get_logger(order.correlation_id)
        log.info("sending_cart_recovery", order_id=order.order_id)
        
        return await self._send_notification(
            order=order,
            notification_type=NotificationType.CART_RECOVERY,
            template_data={
                "recovery_url": recovery_url,
                "business_name": order.business_name,
            },
        )
    
    async def on_production_started(self, order: ProductionOrder) -> NotificationRecord:
        """Send production started email"""
        log = self._get_logger(order.correlation_id)
        log.info("sending_production_started", order_id=order.order_id)
        
        return await self._send_notification(
            order=order,
            notification_type=NotificationType.PRODUCTION_STARTED,
            template_data={
                "order_id": order.order_id,
                "estimated_completion": (
                    order.estimated_delivery.strftime("%B %d")
                    if order.estimated_delivery else "Soon"
                ),
            },
        )
    
    async def on_milestone_completed(
        self,
        order: ProductionOrder,
        phase_name: str,
        progress: int,
    ) -> NotificationRecord:
        """Send milestone update email"""
        log = self._get_logger(order.correlation_id)
        log.info("sending_milestone", order_id=order.order_id, phase=phase_name, progress=progress)
        
        return await self._send_notification(
            order=order,
            notification_type=NotificationType.MILESTONE_UPDATE,
            template_data={
                "order_id": order.order_id,
                "phase_name": phase_name,
                "progress_percent": progress,
            },
        )
    
    async def on_production_completed(
        self,
        order: ProductionOrder,
        video_key: str,
        formats: list[str] = None,
    ) -> tuple[DeliveryToken, NotificationRecord]:
        """
        SECURE DELIVERY: Create portal token and send delivery email.
        
        The email does NOT contain the S3 link directly.
        Instead, it contains a portal link that the user must visit.
        The portal then exchanges the token for a short-lived download URL.
        """
        log = self._get_logger(order.correlation_id)
        log.info("initiating_secure_delivery", order_id=order.order_id, video_key=video_key)
        
        # Generate secure token
        raw_token, token_hash = self._generate_token()
        
        # Determine limits based on tier
        if order.payment_tier == PaymentTier.ENTERPRISE:
            max_downloads = settings.ENTERPRISE_MAX_DOWNLOADS
            expiry_hours = settings.PORTAL_TOKEN_EXPIRY_HOURS * 2  # 14 days for enterprise
        else:
            max_downloads = settings.MAX_DOWNLOADS_PER_TOKEN
            expiry_hours = settings.PORTAL_TOKEN_EXPIRY_HOURS
        
        # Create token record
        token = DeliveryToken(
            token_hash=token_hash,
            order_id=order.order_id,
            correlation_id=order.correlation_id,
            payment_tier=order.payment_tier,
            max_downloads=max_downloads,
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours),
            video_key=video_key,
            formats_available=formats or ["mp4_1080p"],
        )
        
        await self.tokens.save(token)
        
        log.info("delivery_token_created",
                 token_id=token.token_id,
                 max_downloads=max_downloads,
                 expires_at=token.expires_at.isoformat())
        
        # Build portal URL (NOT the S3 URL)
        portal_download_url = f"{settings.PORTAL_URL}/download?token={raw_token}"
        
        # Send delivery email
        notification = await self._send_notification(
            order=order,
            notification_type=NotificationType.DELIVERY_FINAL,
            template_data={
                "order_id": order.order_id,
                "download_url": portal_download_url,  # Portal link, not S3
                "expires_in": f"{expiry_hours // 24} days",
                "max_downloads": max_downloads,
                "formats_available": ", ".join(formats or ["MP4 (1080p)"]),
            },
        )
        
        return token, notification
    
    # =========================================================================
    # TOKEN EXCHANGE (Just-in-Time Download)
    # =========================================================================
    
    async def exchange_token_for_download(
        self,
        raw_token: str,
        ip_address: str,
        user_agent: str,
        referer: str = None,
    ) -> dict:
        """
        Exchange portal token for short-lived download URL.
        
        This is called when the user clicks the portal link.
        Validates the token, logs the attempt, and returns a 15-minute S3/CloudFront URL.
        
        Returns:
            {
                "success": True,
                "download_url": "https://...",
                "expires_in_seconds": 900,
                "remaining_downloads": 9,
            }
        """
        token_hash = self._hash_token(raw_token)
        token = await self.tokens.get_by_hash(token_hash)
        
        correlation_id = token.correlation_id if token else str(uuid.uuid4())
        log = self._get_logger(correlation_id)
        
        # Prepare audit attempt
        attempt = DownloadAttempt(
            token_id=token.token_id if token else "unknown",
            order_id=token.order_id if token else "unknown",
            correlation_id=correlation_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            success=False,
        )
        
        # Validate token
        if not token:
            attempt.failure_reason = "token_not_found"
            await self.audit.log_attempt(attempt)
            log.warning("token_exchange_failed", reason="not_found", ip=ip_address)
            return {"success": False, "error": "Invalid or expired token"}
        
        if not token.is_valid:
            if token.status == TokenStatus.EXPIRED or datetime.utcnow() > token.expires_at:
                attempt.failure_reason = "token_expired"
                reason = "expired"
            elif token.status == TokenStatus.REVOKED:
                attempt.failure_reason = "token_revoked"
                reason = "revoked"
            elif token.download_count >= token.max_downloads:
                attempt.failure_reason = "downloads_exhausted"
                reason = "max_downloads_reached"
            else:
                attempt.failure_reason = "token_invalid"
                reason = "invalid"
            
            await self.audit.log_attempt(attempt)
            log.warning("token_exchange_failed",
                       reason=reason,
                       token_id=token.token_id,
                       ip=ip_address)
            return {"success": False, "error": f"Token {reason}"}
        
        # Generate short-lived download URL
        try:
            expires_in = settings.DOWNLOAD_LINK_EXPIRY_MINUTES * 60
            filename = f"{token.order_id}.mp4"
            
            download_url = await self.url_generator.generate_download_url(
                key=token.video_key,
                filename=filename,
                expires_in_seconds=expires_in,
            )
            
            # Record download
            updated_token = token.record_download()
            await self.tokens.update(updated_token)
            
            # Log success
            attempt.success = True
            attempt.presigned_url_generated = True
            await self.audit.log_attempt(attempt)
            
            log.info("token_exchanged",
                     token_id=token.token_id,
                     order_id=token.order_id,
                     remaining_downloads=updated_token.remaining_downloads,
                     ip=ip_address)
            
            return {
                "success": True,
                "download_url": download_url,
                "expires_in_seconds": expires_in,
                "remaining_downloads": updated_token.remaining_downloads,
                "filename": filename,
            }
            
        except Exception as e:
            attempt.failure_reason = str(e)
            await self.audit.log_attempt(attempt)
            log.error("url_generation_failed", error=str(e), token_id=token.token_id)
            return {"success": False, "error": "Failed to generate download URL"}
    
    # =========================================================================
    # SENDGRID WEBHOOK HANDLING
    # =========================================================================
    
    async def handle_sendgrid_webhook(
        self,
        events: list[dict],
        signature: str = None,
    ) -> dict:
        """
        Handle SendGrid webhook events for email tracking.
        
        Tracks: delivered, open, click, bounce, dropped, spam_report
        Triggers alerts for bounces/drops on critical emails.
        """
        log = self._get_logger()
        results = {"processed": 0, "alerts": 0, "errors": 0}
        
        for event_data in events:
            try:
                event = self._parse_sendgrid_event(event_data)
                if not event:
                    continue
                
                # Update notification status
                await self._update_notification_from_webhook(event)
                
                # Check for delivery failures
                if event.event_type in ("bounce", "dropped"):
                    await self._handle_delivery_failure(event)
                    results["alerts"] += 1
                
                results["processed"] += 1
                
            except Exception as e:
                log.error("sendgrid_webhook_error", error=str(e), event=event_data)
                results["errors"] += 1
        
        log.info("sendgrid_webhooks_processed", **results)
        return results
    
    def _parse_sendgrid_event(self, data: dict) -> Optional[SendGridWebhookEvent]:
        """Parse raw SendGrid webhook payload"""
        try:
            return SendGridWebhookEvent(
                event_type=data.get("event", "unknown"),
                email=data.get("email", ""),
                timestamp=datetime.fromtimestamp(data.get("timestamp", 0)),
                sg_message_id=data.get("sg_message_id", ""),
                reason=data.get("reason"),
                ip=data.get("ip"),
                user_agent=data.get("useragent"),
                url=data.get("url"),
                raw_payload=data,
            )
        except Exception:
            return None
    
    async def _update_notification_from_webhook(self, event: SendGridWebhookEvent):
        """Update notification record from SendGrid event"""
        status_map = {
            "delivered": (DeliveryStatus.DELIVERED, "delivered_at"),
            "open": (DeliveryStatus.OPENED, "opened_at"),
            "click": (DeliveryStatus.CLICKED, "clicked_at"),
            "bounce": (DeliveryStatus.BOUNCED, "bounced_at"),
            "dropped": (DeliveryStatus.DROPPED, None),
        }
        
        if event.event_type in status_map:
            status, timestamp_field = status_map[event.event_type]
            kwargs = {}
            if timestamp_field:
                kwargs[timestamp_field] = event.timestamp
            
            await self.notifications.update_status(
                event.sg_message_id,
                status,
                **kwargs,
            )
    
    async def _handle_delivery_failure(self, event: SendGridWebhookEvent):
        """Handle bounce/drop with alerting"""
        log = self._get_logger()
        
        # Get bounce history
        since = datetime.utcnow() - timedelta(days=7)
        recent_bounces = await self.notifications.get_bounces_for_email(event.email, since)
        
        # Determine severity
        if len(recent_bounces) >= settings.BOUNCE_ALERT_THRESHOLD:
            severity = "high"
        elif event.event_type == "dropped":
            severity = "medium"
        else:
            severity = "low"
        
        # Get notification record for context
        notification = await self.notifications.get_by_message_id(event.sg_message_id)
        
        alert = DeliveryAlert(
            alert_type=event.event_type,
            severity=severity,
            order_id=notification.order_id if notification else "unknown",
            correlation_id=notification.correlation_id if notification else str(uuid.uuid4()),
            recipient_email=event.email,
            message=f"Email {event.event_type}: {event.reason or 'No reason provided'}",
            metadata={
                "bounce_count": len(recent_bounces) + 1,
                "event_timestamp": event.timestamp.isoformat(),
                "notification_type": notification.notification_type.value if notification else "unknown",
            },
        )
        
        await self.alerts.send_alert(alert)
        
        log.warning("delivery_failure_alert",
                   alert_type=event.event_type,
                   severity=severity,
                   email=event.email,
                   bounce_count=len(recent_bounces) + 1)
    
    # =========================================================================
    # EMAIL SENDING
    # =========================================================================
    
    async def _send_notification(
        self,
        order: ProductionOrder,
        notification_type: NotificationType,
        template_data: dict,
    ) -> NotificationRecord:
        """Send email with smart template routing"""
        log = self._get_logger(order.correlation_id)
        
        # Get template and branding for tier
        template_id = self.templates.get_template_id(notification_type, order.payment_tier)
        full_data = self.templates.build_template_data(
            notification_type, order.payment_tier, template_data
        )
        
        # Create notification record
        record = NotificationRecord(
            order_id=order.order_id,
            correlation_id=order.correlation_id,
            notification_type=notification_type,
            recipient_email=order.delivery_email,
            payment_tier=order.payment_tier,
            template_id=template_id,
        )
        
        try:
            # In production: Actually send via SendGrid
            # from sendgrid import SendGridAPIClient
            # from sendgrid.helpers.mail import Mail
            #
            # sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            # message = Mail(
            #     from_email=settings.SENDGRID_FROM_EMAIL,
            #     to_emails=order.delivery_email,
            # )
            # message.template_id = template_id
            # message.dynamic_template_data = full_data
            # response = sg.send(message)
            # record.sendgrid_message_id = response.headers.get("X-Message-Id")
            
            # Mock for demo
            record.sendgrid_message_id = f"sg-{uuid.uuid4().hex[:16]}"
            record.status = DeliveryStatus.SENT
            record.sent_at = datetime.utcnow()
            
            await self.notifications.save(record)
            
            log.info("notification_sent",
                     notification_type=notification_type.value,
                     template_id=template_id,
                     tier=order.payment_tier.value,
                     message_id=record.sendgrid_message_id)
            
            return record
            
        except Exception as e:
            record.status = DeliveryStatus.FAILED
            record.last_error = str(e)
            await self.notifications.save(record)
            
            log.error("notification_failed",
                     notification_type=notification_type.value,
                     error=str(e))
            raise
    
    # =========================================================================
    # ADMIN/UTILITY METHODS
    # =========================================================================
    
    async def revoke_token(self, token_id: str, reason: str = None) -> bool:
        """Revoke a delivery token (e.g., on refund)"""
        log = self._get_logger()
        success = await self.tokens.revoke(token_id)
        log.info("token_revoked", token_id=token_id, reason=reason, success=success)
        return success
    
    async def get_download_audit(self, order_id: str) -> list[DownloadAttempt]:
        """Get download audit trail for order"""
        return await self.audit.get_attempts_for_order(order_id)
    
    async def get_pending_alerts(self) -> list[DeliveryAlert]:
        """Get unacknowledged alerts"""
        return await self.alerts.get_unacknowledged()
    
    async def get_token_status(self, order_id: str) -> list[dict]:
        """Get token status for order"""
        tokens = await self.tokens.get_by_order(order_id)
        return [
            {
                "token_id": t.token_id,
                "status": t.status.value,
                "downloads": t.download_count,
                "max_downloads": t.max_downloads,
                "remaining": t.remaining_downloads,
                "expires_at": t.expires_at.isoformat(),
                "is_valid": t.is_valid,
            }
            for t in tokens
        ]


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

async def main():
    """Demo the legendary Delivery Agent."""
    
    agent = DeliveryAgent()
    
    # Create sample order
    order = ProductionOrder(
        order_id="ORD-12345678",
        brief_id="BRF-87654321",
        delivery_email="customer@example.com",
        payment_tier=PaymentTier.ENTERPRISE,  # White Glove!
        amount_paid=15000,
        estimated_delivery=datetime.utcnow() + timedelta(days=2),
        business_name="MegaCorp Industries",
    )
    
    print("=" * 70)
    print("LEGENDARY DELIVERY AGENT - SECURE ENTERPRISE ASSET DELIVERY")
    print("=" * 70)
    
    # 1. Payment confirmed
    print("\n1. Payment Confirmed Email...")
    notif = await agent.on_payment_confirmed(order)
    print(f"   ✅ Template: {notif.template_id}")
    print(f"   Tier: {notif.payment_tier.value} (Enterprise = White Glove branding)")
    
    # 2. Production started
    print("\n2. Production Started Email...")
    notif = await agent.on_production_started(order)
    print(f"   ✅ Sent to: {notif.recipient_email}")
    
    # 3. Production completed (SECURE DELIVERY)
    print("\n3. Production Completed - Secure Delivery...")
    token, notif = await agent.on_production_completed(
        order, "videos/ORD-12345678/final_1080p.mp4",
        formats=["MP4 (1080p)", "MP4 (4K)", "MOV (ProRes)"]
    )
    print(f"   ✅ Token created: {token.token_id}")
    print(f"   Max downloads: {token.max_downloads}")
    print(f"   Expires: {token.expires_at}")
    print(f"   📧 Email contains PORTAL link, not S3 link!")
    
    # 4. Simulate token exchange (user clicks portal link)
    print("\n4. User Clicks Download Link - Token Exchange...")
    
    # Get raw token (in real flow, this comes from URL query param)
    # For demo, we'll regenerate since we only stored the hash
    raw_token, token_hash = agent._generate_token()
    
    # Save a new token with known raw value for demo
    demo_token = DeliveryToken(
        token_hash=token_hash,
        order_id=order.order_id,
        correlation_id=order.correlation_id,
        payment_tier=order.payment_tier,
        max_downloads=50,
        expires_at=datetime.utcnow() + timedelta(hours=336),
        video_key="videos/ORD-12345678/final_1080p.mp4",
        formats_available=["mp4_1080p", "mp4_4k", "mov_prores"],
    )
    await agent.tokens.save(demo_token)
    
    # Exchange token
    result = await agent.exchange_token_for_download(
        raw_token=raw_token,
        ip_address="203.0.113.42",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        referer="https://portal.videoforge.ai/download",
    )
    
    if result["success"]:
        print(f"   ✅ Download URL generated!")
        print(f"   URL (truncated): {result['download_url'][:60]}...")
        print(f"   Expires in: {result['expires_in_seconds']} seconds (15 min)")
        print(f"   Remaining downloads: {result['remaining_downloads']}")
    else:
        print(f"   ❌ Error: {result['error']}")
    
    # 5. Check audit trail
    print("\n5. Download Audit Trail...")
    audit = await agent.get_download_audit(order.order_id)
    print(f"   Total attempts: {len(audit)}")
    for attempt in audit[:3]:
        print(f"   - {attempt.timestamp.isoformat()}: {'✅' if attempt.success else '❌'}")
        print(f"     IP: {attempt.ip_address}, UA: {attempt.user_agent[:30]}...")
    
    # 6. Token status
    print("\n6. Token Status...")
    status = await agent.get_token_status(order.order_id)
    for s in status:
        print(f"   Token {s['token_id'][:8]}...: {s['downloads']}/{s['max_downloads']} downloads")
        print(f"   Status: {s['status']}, Valid: {s['is_valid']}")
    
    # 7. Simulate SendGrid webhook (bounce)
    print("\n7. Simulating Email Bounce Webhook...")
    webhook_result = await agent.handle_sendgrid_webhook([
        {
            "event": "bounce",
            "email": "customer@example.com",
            "timestamp": int(datetime.utcnow().timestamp()),
            "sg_message_id": notif.sendgrid_message_id,
            "reason": "550 5.1.1 The email account does not exist",
        }
    ])
    print(f"   Processed: {webhook_result['processed']}")
    print(f"   Alerts triggered: {webhook_result['alerts']}")
    
    # 8. Check alerts
    print("\n8. Pending Alerts...")
    alerts = await agent.get_pending_alerts()
    for alert in alerts:
        print(f"   🚨 [{alert.severity.upper()}] {alert.alert_type}: {alert.message}")
    
    print("\n" + "=" * 70)
    print("ARCHITECTURE SUMMARY")
    print("=" * 70)
    print("✅ Just-in-Time Downloads: Portal tokens, not direct S3 links")
    print("✅ Secure Token Exchange: HMAC-SHA256 hashed, usage limited")
    print("✅ CloudFront CDN: Signed URLs with custom policy")
    print("✅ SendGrid Webhooks: Bounce/drop detection with alerting")
    print("✅ Download Audit Trail: IP, User-Agent, timestamp logged")
    print("✅ Smart Templates: Tier-based branding (Enterprise = White Glove)")
    print("✅ Token Revocation: Can revoke on refund/fraud")


if __name__ == "__main__":
    asyncio.run(main())
