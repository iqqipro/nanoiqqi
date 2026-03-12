"""Message bus module for decoupled channel-agent communication."""

from nanoiqqi.bus.events import InboundMessage, OutboundMessage
from nanoiqqi.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
