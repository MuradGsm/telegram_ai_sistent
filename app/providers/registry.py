from app.core.enums import ChannelType
from app.providers.base import ChannelProvider
from app.providers.telegram_provider import TelegramProvider
from app.providers.web_provider import WebProvider
 
_PROVIDERS: dict[ChannelType, ChannelProvider] = {
    ChannelType.TELEGRAM: TelegramProvider(),
    ChannelType.WEB: WebProvider(),
}
 
 
def get_provider(channel_type: ChannelType) -> ChannelProvider:
    provider = _PROVIDERS.get(channel_type)
    if provider is None:
        raise NotImplementedError(f"No provider registered for {channel_type}")
    return provider
 