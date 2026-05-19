"""
Bot API Service Classes for Magic Bot AI
Provides integration with various messaging platforms
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
        """Log an event for analytics"""
        # This would typically send to an analytics service
        logger.info(f"Bot Event: {event_type} - {event_data or {}}")


class TelegramBotService(BotAPIService):
    """Telegram Bot API integration"""
    
    def __init__(self, bot_config: Dict[str, Any]):
        super().__init__(bot_config)
        self.api_url = f"https://api.telegram.org/bot{self.token}"
    
    def send_message(self, message: str, recipient: str, **kwargs) -> Dict[str, Any]:
        """
        Send a message to a Telegram chat
        
        Args:
            message: Text message to send
            recipient: Telegram chat ID (as string)
            **kwargs: Additional parameters (parse_mode, disable_web_page_preview, etc.)
        
        Returns:
            Dictionary with API response
        """
        try:
            payload = {
                "chat_id": recipient,  # recipient parameter is the chat_id for Telegram
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
                    'chat_id': recipient,  # Use recipient variable (which is the chat_id)
                    'message_length': len(message),
                    'platform': 'telegram'
                })
                return {
                    'success': True,
                    'message_id': result['result']['message_id'],
                    'chat_id': recipient,  # Use recipient variable
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
    
    def get_updates(self, offset: Optional[int] = None, limit: int = 100, timeout: int = 0) -> Dict[str, Any]:
        """Get recent updates (messages) for the bot
        
        Args:
            offset: Identifier of the first update to be returned
            limit: Limits the number of updates to be retrieved (1-100)
            timeout: Timeout in seconds for long polling (0-50)
        """
        try:
            params = {'limit': limit, 'timeout': timeout}
            if offset:
                params['offset'] = offset
            
            # Use timeout + 5 seconds for HTTP timeout to be safe
            http_timeout = timeout + 5 if timeout > 0 else 10
            response = requests.get(f"{self.api_url}/getUpdates", params=params, timeout=http_timeout)
            result = response.json()
            
            if result.get('ok'):
                return {
                    'success': True,
                    'updates': result['result'],
                    'next_offset': result['result'][-1]['update_id'] + 1 if result['result'] else offset
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
    
    def set_webhook(self, url: str) -> Dict[str, Any]:
        """Set webhook URL for receiving updates"""
        try:
            response = requests.post(
                f"{self.api_url}/setWebhook",
                json={'url': url},
                timeout=10
            )
            result = response.json()
            
            if result.get('ok'):
                return {
                    'success': True,
                    'message': 'Webhook set successfully'
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


class DiscordBotService(BotAPIService):
    """Discord Bot API integration"""
    
    def __init__(self, bot_config: Dict[str, Any]):
        super().__init__(bot_config)
        self.api_url = "https://discord.com/api/v10"
        self.headers = {
            'Authorization': f'Bot {self.token}',
            'Content-Type': 'application/json'
        }
    
    def send_message(self, message: str, recipient: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a Discord channel"""
        try:
            payload = {
                'content': message,
                **kwargs
            }
            
            response = requests.post(
                f"{self.api_url}/channels/{recipient}/messages",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                self.log_event('message_sent', {
                    'channel_id': recipient,
                    'platform': 'discord'
                })
                return {
                    'success': True,
                    'message_id': result['id'],
                    'channel_id': channel_id,
                    'timestamp': result['timestamp']
                }
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"Discord API error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def get_bot_info(self) -> Dict[str, Any]:
        """Get information about the Discord bot"""
        try:
            response = requests.get(
                f"{self.api_url}/users/@me",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'bot_info': response.json(),
                    'platform': 'discord'
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


class SlackBotService(BotAPIService):
    """Slack Bot API integration"""
    
    def __init__(self, bot_config: Dict[str, Any]):
        super().__init__(bot_config)
        self.api_url = "https://slack.com/api"
    
    def send_message(self, message: str, recipient: str, **kwargs) -> Dict[str, Any]:
        """Send a message to a Slack channel"""
        try:
            payload = {
                'token': self.token,
                'channel': recipient,  # recipient is the channel for Slack
                'text': message,
                **kwargs
            }
            
            response = requests.post(
                f"{self.api_url}/chat.postMessage",
                data=payload,
                timeout=10
            )
            
            result = response.json()
            
            if result.get('ok'):
                self.log_event('message_sent', {
                    'channel': recipient,
                    'platform': 'slack'
                })
                return {
                    'success': True,
                    'message_ts': result['ts'],
                    'channel': recipient
                }
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Slack API error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def get_bot_info(self) -> Dict[str, Any]:
        """Get information about the Slack bot"""
        try:
            response = requests.post(
                f"{self.api_url}/auth.test",
                data={'token': self.token},
                timeout=10
            )
            
            result = response.json()
            
            if result.get('ok'):
                return {
                    'success': True,
                    'bot_info': result,
                    'platform': 'slack'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error')
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


class BotServiceFactory:
    """Factory class to create bot service instances"""
    
    @staticmethod
    def create_service(platform: str, bot_config: Dict[str, Any]) -> BotAPIService:
        """
        Create a bot service instance based on platform
        
        Args:
            platform: 'telegram', 'discord', or 'slack'
            bot_config: Bot configuration dictionary
        
        Returns:
            BotAPIService instance
        
        Raises:
            BotServiceError: If platform is not supported
        """
        platform = platform.lower()
        
        if platform == 'telegram':
            return TelegramBotService(bot_config)
        elif platform == 'discord':
            return DiscordBotService(bot_config)
        elif platform == 'slack':
            return SlackBotService(bot_config)
        else:
            raise BotServiceError(f"Unsupported platform: {platform}")
    
    @staticmethod
    def get_supported_platforms() -> list:
        """Get list of supported platforms"""
        return ['telegram', 'discord', 'slack']


# Utility functions
def test_bot_connection(platform: str, token: str) -> Dict[str, Any]:
    """Test connection to bot service"""
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