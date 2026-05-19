"""
FIXED Telegram Bot Service - No chat_id variable issues
"""

import requests
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BotServiceError(Exception):
    """Custom exception for bot service errors"""
    pass


class BotAPIService(ABC):
    """Abstract base class for bot API services"""
    
    def __init__(self, bot_config: Dict[str, Any]):
        self.config = bot_config
        self.token = bot_config.get('token', '')
        self.name = bot_config.get('name', 'Unnamed Bot')
        self.validate_config()
    
    def validate_config(self):
        """Validate required configuration"""
        if not self.token:
            raise BotServiceError("Bot token is required")
    
    @abstractmethod
    def send_message(self, message: str, recipient: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a recipient"""
        pass
    
    @abstractmethod
    def get_bot_info(self) -> Dict[str, Any]:
        """Get information about the bot"""
        pass
    
    def test_connection(self) -> bool:
        """Test if the bot service is reachable"""
        try:
            info = self.get_bot_info()
            return 'error' not in info
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def log_event(self, event_type: str, event_data: Dict[str, Any] = None):
        """Log an event (can be overridden for actual logging)"""
        logger.info(f"Logged event: {event_type} for bot {self.name}")


class TelegramBotService(BotAPIService):
    """Telegram Bot API integration - FIXED VERSION"""
    
    def __init__(self, bot_config: Dict[str, Any]):
        super().__init__(bot_config)
        self.api_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(self, message: str, recipient: str, **kwargs) -> Dict[str, Any]:
        """
        Send a message to a Telegram chat
        
        Args:
            message: Text message to send
            recipient: Telegram chat ID (as string)
            **kwargs: Additional parameters
        
        Returns:
            Dictionary with API response
        """
        try:
            payload = {
                "chat_id": recipient,  # recipient is the chat_id
                "text": message,
                **kwargs
            }
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            result = response.json()
            
            if result.get('ok'):
                self.log_event('message_sent', {
                    'chat_id': recipient,  # Use recipient
                    'message_length': len(message),
                    'platform': 'telegram'
                })
                return {
                    'success': True,
                    'message_id': result['result']['message_id'],
                    'chat_id': recipient,  # Use recipient
                    'timestamp': result['result']['date']
                }
            else:
                error_msg = result.get('description', 'Unknown error')
                logger.error(f"Telegram API error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'error_code': result.get('error_code')
                }
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def get_bot_info(self) -> Dict[str, Any]:
        """Get information about the Telegram bot"""
        try:
            response = requests.get(f"{self.api_url}/getMe", timeout=10)
            result = response.json()
            
            if result.get('ok'):
                return {
                    'success': True,
                    'bot_info': result['result'],
                    'platform': 'telegram'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('description', 'Unknown error')
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


class BotServiceFactory:
    """Factory for creating bot services"""
    
    @staticmethod
    def create_service(platform: str, bot_config: Dict[str, Any]) -> BotAPIService:
        """Create a bot service for the specified platform"""
        if platform == 'telegram':
            return TelegramBotService(bot_config)
        elif platform == 'discord':
            # Simplified Discord service
            class DiscordBotService(BotAPIService):
                def send_message(self, message, recipient, **kwargs):
                    return {'success': False, 'error': 'Discord not fully implemented'}
                def get_bot_info(self):
                    return {'success': False, 'error': 'Discord not fully implemented'}
            return DiscordBotService(bot_config)
        elif platform == 'slack':
            # Simplified Slack service
            class SlackBotService(BotAPIService):
                def send_message(self, message, recipient, **kwargs):
                    return {'success': False, 'error': 'Slack not fully implemented'}
                def get_bot_info(self):
                    return {'success': False, 'error': 'Slack not fully implemented'}
            return SlackBotService(bot_config)
        else:
            raise BotServiceError(f"Unsupported platform: {platform}")
    
    @staticmethod
    def get_supported_platforms() -> list:
        """Get list of supported platforms"""
        return ['telegram', 'discord', 'slack']


def test_bot_connection(platform: str, token: str) -> Dict[str, Any]:
    """Test connection to a bot"""
    try:
        service = BotServiceFactory.create_service(
            platform,
            {'token': token, 'name': 'Test Bot'}
        )
        return service.get_bot_info()
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def send_bot_message(platform: str, token: str, message: str, recipient: str, **kwargs) -> Dict[str, Any]:
    """Send a message using bot service"""
    try:
        service = BotServiceFactory.create_service(
            platform,
            {'token': token, 'name': 'Message Bot'}
        )
        return service.send_message(message, recipient, **kwargs)
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }