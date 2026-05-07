from abc import ABC, abstractmethod


class BasePublisher(ABC):

    @abstractmethod
    async def publish_carousel(self, images: list[str], caption: str, hashtags: list[str] = None) -> bool: ...

    @abstractmethod
    async def publish_reel(self, video: str, caption: str, hashtags: list[str] = None) -> bool: ...

    @abstractmethod
    async def publish_story(self, image: str, poll_config: dict = None) -> bool: ...
