"""
Analytics System for Magic Bot AI
Handles bot event logging, statistics, and reporting
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalyticsError(Exception):
    """Custom exception for analytics errors"""
    pass


class BotAnalytics:
    """Bot analytics management"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.init_tables()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_tables(self):
        """Initialize analytics tables if they don't exist"""
        conn = self.get_connection()
        
        # Bot analytics table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_analytics_bot_id ON bot_analytics(bot_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_analytics_timestamp ON bot_analytics(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bot_analytics_event_type ON bot_analytics(event_type)")
        
        conn.commit()
        conn.close()
    
    def log_event(self, bot_id: int, event_type: str, event_data: Dict[str, Any] = None) -> bool:
        """
        Log an event for analytics
        
        Args:
            bot_id: ID of the bot
            event_type: Type of event (message_sent, command_executed, error, etc.)
            event_data: Additional event data as dictionary
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            
            # Log the event
            conn.execute("""
                INSERT INTO bot_analytics (bot_id, event_type, event_data)
                VALUES (?, ?, ?)
            """, (bot_id, event_type, json.dumps(event_data) if event_data else None))
            
            # Update bot usage stats
            conn.execute("""
                UPDATE bots 
                SET last_used = CURRENT_TIMESTAMP,
                    usage_count = usage_count + 1
                WHERE id = ?
            """, (bot_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Logged event: {event_type} for bot {bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            return False
    
    def get_bot_events(self, bot_id: int, 
                      start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None,
                      event_type: Optional[str] = None,
                      limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get events for a specific bot
        
        Args:
            bot_id: ID of the bot
            start_date: Start date for filtering
            end_date: End date for filtering
            event_type: Filter by event type
            limit: Maximum number of events to return
        
        Returns:
            List of event dictionaries
        """
        try:
            conn = self.get_connection()
            
            query = "SELECT * FROM bot_analytics WHERE bot_id = ?"
            params = [bot_id]
            
            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date.isoformat())
            
            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date.isoformat())
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(query, params)
            events = [dict(row) for row in cursor.fetchall()]
            
            # Parse event_data JSON
            for event in events:
                if event['event_data']:
                    try:
                        event['event_data'] = json.loads(event['event_data'])
                    except:
                        pass
            
            conn.close()
            return events
            
        except Exception as e:
            logger.error(f"Failed to get bot events: {e}")
            return []
    
    def get_event_summary(self, bot_id: int, 
                         days: int = 7) -> Dict[str, Any]:
        """
        Get event summary for a bot
        
        Args:
            bot_id: ID of the bot
            days: Number of days to look back
        
        Returns:
            Dictionary with event summary
        """
        try:
            conn = self.get_connection()
            
            # Get event counts by type
            cursor = conn.execute("""
                SELECT event_type, COUNT(*) as count
                FROM bot_analytics 
                WHERE bot_id = ? AND timestamp > datetime('now', ?)
                GROUP BY event_type
                ORDER BY count DESC
            """, (bot_id, f'-{days} days'))
            
            event_counts = {row['event_type']: row['count'] for row in cursor.fetchall()}
            
            # Get daily activity
            cursor = conn.execute("""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM bot_analytics 
                WHERE bot_id = ? AND timestamp > datetime('now', ?)
                GROUP BY DATE(timestamp)
                ORDER BY date
            """, (bot_id, f'-{days} days'))
            
            daily_activity = [{'date': row['date'], 'count': row['count']} 
                            for row in cursor.fetchall()]
            
            # Get peak hour
            cursor = conn.execute("""
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
                FROM bot_analytics 
                WHERE bot_id = ? AND timestamp > datetime('now', ?)
                GROUP BY strftime('%H', timestamp)
                ORDER BY count DESC
                LIMIT 1
            """, (bot_id, f'-{days} days'))
            
            peak_hour_row = cursor.fetchone()
            peak_hour = peak_hour_row['hour'] if peak_hour_row else None
            
            conn.close()
            
            return {
                'event_counts': event_counts,
                'daily_activity': daily_activity,
                'peak_hour': peak_hour,
                'total_events': sum(event_counts.values()),
                'days_analyzed': days
            }
            
        except Exception as e:
            logger.error(f"Failed to get event summary: {e}")
            return {}
    
    def get_bot_usage_stats(self, bot_id: int) -> Dict[str, Any]:
        """
        Get usage statistics for a bot
        
        Args:
            bot_id: ID of the bot
        
        Returns:
            Dictionary with usage statistics
        """
        try:
            conn = self.get_connection()
            
            # Get bot info
            bot = conn.execute("SELECT * FROM bots WHERE id = ?", (bot_id,)).fetchone()
            if not bot:
                conn.close()
                return {}
            
            # Get time-based stats
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(DISTINCT DATE(timestamp)) as active_days,
                    MIN(timestamp) as first_event,
                    MAX(timestamp) as last_event,
                    AVG(
                        CASE WHEN event_type = 'message_sent' 
                        THEN json_extract(event_data, '$.message_length') 
                        ELSE NULL END
                    ) as avg_message_length
                FROM bot_analytics 
                WHERE bot_id = ?
            """, (bot_id,))
            
            stats_row = cursor.fetchone()
            
            # Get event type distribution
            cursor = conn.execute("""
                SELECT event_type, COUNT(*) as count,
                       COUNT(*) * 100.0 / (SELECT COUNT(*) FROM bot_analytics WHERE bot_id = ?) as percentage
                FROM bot_analytics 
                WHERE bot_id = ?
                GROUP BY event_type
                ORDER BY count DESC
            """, (bot_id, bot_id))
            
            event_distribution = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            stats = dict(stats_row) if stats_row else {}
            stats['event_distribution'] = event_distribution
            stats['bot_name'] = bot['name']
            stats['bot_platform'] = bot['messaging']
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get bot usage stats: {e}")
            return {}
    
    def get_user_analytics(self, user_id: int, 
                          days: int = 30) -> Dict[str, Any]:
        """
        Get analytics for all bots owned by a user
        
        Args:
            user_id: ID of the user
            days: Number of days to look back
        
        Returns:
            Dictionary with user analytics
        """
        try:
            conn = self.get_connection()
            
            # Get user's bots
            bots = conn.execute("SELECT id, name FROM bots WHERE user_id = ?", (user_id,)).fetchall()
            
            analytics = {
                'total_bots': len(bots),
                'bots': [],
                'summary': {
                    'total_events': 0,
                    'active_bots': 0,
                    'total_messages': 0
                }
            }
            
            for bot in bots:
                bot_id = bot['id']
                
                # Get bot stats
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as event_count,
                        COUNT(CASE WHEN event_type = 'message_sent' THEN 1 END) as message_count,
                        MAX(timestamp) as last_activity
                    FROM bot_analytics 
                    WHERE bot_id = ? AND timestamp > datetime('now', ?)
                """, (bot_id, f'-{days} days'))
                
                stats = cursor.fetchone()
                
                bot_analytics = {
                    'id': bot_id,
                    'name': bot['name'],
                    'event_count': stats['event_count'] if stats else 0,
                    'message_count': stats['message_count'] if stats else 0,
                    'last_activity': stats['last_activity'] if stats else None,
                    'is_active': bool(stats and stats['event_count'] > 0)
                }
                
                analytics['bots'].append(bot_analytics)
                analytics['summary']['total_events'] += bot_analytics['event_count']
                analytics['summary']['total_messages'] += bot_analytics['message_count']
                if bot_analytics['is_active']:
                    analytics['summary']['active_bots'] += 1
            
            # Get activity trend
            cursor = conn.execute("""
                SELECT DATE(ba.timestamp) as date, COUNT(*) as count
                FROM bot_analytics ba
                JOIN bots b ON ba.bot_id = b.id
                WHERE b.user_id = ? AND ba.timestamp > datetime('now', ?)
                GROUP BY DATE(ba.timestamp)
                ORDER BY date
            """, (user_id, f'-{days} days'))
            
            activity_trend = [{'date': row['date'], 'count': row['count']} 
                            for row in cursor.fetchall()]
            
            analytics['activity_trend'] = activity_trend
            
            conn.close()
            return analytics
            
        except Exception as e:
            logger.error(f"Failed to get user analytics: {e}")
            return {}
    
    def export_analytics(self, bot_id: int, 
                        format: str = 'json',
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> str:
        """
        Export analytics data
        
        Args:
            bot_id: ID of the bot
            format: Export format ('json' or 'csv')
            start_date: Start date for filtering
            end_date: End date for filtering
        
        Returns:
            Exported data as string
        """
        try:
            events = self.get_bot_events(bot_id, start_date, end_date, limit=10000)
            
            if format.lower() == 'json':
                return json.dumps(events, indent=2, default=str)
            
            elif format.lower() == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=['id', 'bot_id', 'event_type', 
                                                          'event_data', 'timestamp'])
                writer.writeheader()
                
                for event in events:
                    row = event.copy()
                    if row['event_data'] and isinstance(row['event_data'], dict):
                        row['event_data'] = json.dumps(row['event_data'])
                    writer.writerow(row)
                
                return output.getvalue()
            
            else:
                raise AnalyticsError(f"Unsupported format: {format}")
                
        except Exception as e:
            logger.error(f"Failed to export analytics: {e}")
            raise AnalyticsError(f"Export failed: {e}")
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """
        Clean up old analytics data
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        try:
            conn = self.get_connection()
            
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            # Delete old analytics data
            conn.execute("""
                DELETE FROM bot_analytics 
                WHERE timestamp < ?
            """, (cutoff_date,))
            
            deleted_count = conn.total_changes
            
            # Vacuum to reclaim space
            conn.execute("VACUUM")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_count} old analytics records")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return 0


# Singleton instance
_analytics_instance = None

def get_analytics(db_path: str = None) -> BotAnalytics:
    """Get analytics instance (singleton)"""
    global _analytics_instance
    
    if _analytics_instance is None:
        if db_path is None:
            # Default to users.db in current directory
            db_path = Path(__file__).parent / "users.db"
        _analytics_instance = BotAnalytics(db_path)
    
    return _analytics_instance


# Convenience functions
def log_bot_event(bot_id: int, event_type: str, event_data: Dict[str, Any] = None):
    """Convenience function to log a bot event"""
    analytics = get_analytics()
    return analytics.log_event(bot_id, event_type, event_data)

def get_bot_analytics(bot_id: int, days: int = 7) -> Dict[str, Any]:
    """Convenience function to get bot analytics"""
    analytics = get_analytics()
    return analytics.get_event_summary(bot_id, days)

def export_bot_data(bot_id: int, format: str = 'json') -> str:
    """Convenience function to export bot data"""
    analytics = get_analytics()
    return analytics.export_analytics(bot_id, format)