#!/usr/bin/env python3
"""
Read JSONL Logs from Webhook URL Directory
Reads the most recent JSONL log file and extracts content.text from log entries
"""

import sys
import os
import sqlite3
import json
import glob
from datetime import datetime
from pathlib import Path

def load_bot_config():
    """Load bot configuration from database including webhook_url"""
    if not os.path.exists('users.db'):
        print("❌ Database not found: users.db")
        return None
    
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    
    bots = conn.execute("""
        SELECT token, name, webhook_url FROM bots 
        WHERE (messaging = 'telegram' OR messaging = 'Telegram') 
        AND token IS NOT NULL 
        AND webhook_url IS NOT NULL 
        AND webhook_url != '' 
        LIMIT 1
    """).fetchall()
    
    conn.close()
    
    if not bots:
        print("❌ No Telegram bots with webhook_url found in database")
        return None
    
    bot = dict(bots[0])
    print(f"✅ Bot: {bot['name']}")
    print(f"✅ Webhook URL from database: {bot['webhook_url']}")
    
    return bot

def extract_log_directory_from_webhook(webhook_url):
    """
    Extract log directory from webhook URL
    
    Expected format: webhook_url might contain path to log directory
    Example: http://localhost:5000/webhook/telegram/... or file:///path/to/logs
    """
    print(f"\n🔍 Parsing webhook URL: {webhook_url}")
    
    # Try to extract directory path
    log_dir = None
    
    # Case 1: URL contains a file path pattern
    if 'file://' in webhook_url:
        log_dir = webhook_url.replace('file://', '')
        print(f"   Found file:// URL, extracting: {log_dir}")
    
    # Case 2: URL contains a local path pattern
    elif webhook_url.startswith('/'):
        log_dir = webhook_url
        print(f"   Found absolute path: {log_dir}")
    
    # Case 3: URL might have a path component that's a directory
    else:
        # Try to extract path from URL
        from urllib.parse import urlparse
        parsed = urlparse(webhook_url)
        
        if parsed.path:
            # Check if path looks like a directory (not ending with common extensions)
            path = parsed.path
            if not any(path.endswith(ext) for ext in ['.py', '.js', '.html', '.php', '.json']):
                log_dir = path
                print(f"   Extracted path from URL: {log_dir}")
            else:
                # Might be a file, get its directory
                log_dir = os.path.dirname(path)
                print(f"   Extracted directory from file URL: {log_dir}")
    
    # If we still don't have a directory, try common log locations
    if not log_dir or not os.path.exists(log_dir):
        print("⚠️  Could not extract valid directory from webhook URL")
        print("   Trying common log locations...")
        
        common_locations = [
            "/var/log/openclaw/",
            os.path.expanduser("~/.openclaw/logs/"),
            "./logs/",
            "./",
            "/tmp/openclaw/",
            "/tmp/",
        ]
        
        for location in common_locations:
            if os.path.exists(location):
                print(f"   Checking: {location}")
                # Look for JSONL files
                jsonl_files = glob.glob(os.path.join(location, "*.jsonl"))
                if jsonl_files:
                    log_dir = location
                    print(f"   ✅ Found JSONL files in: {location}")
                    break
    
    return log_dir

def find_most_recent_jsonl_file(log_dir):
    """Find the most recent JSONL file in the directory"""
    if not log_dir or not os.path.exists(log_dir):
        print(f"❌ Log directory does not exist: {log_dir}")
        return None
    
    print(f"\n📁 Searching for JSONL files in: {log_dir}")
    
    # Find all .jsonl files
    jsonl_files = glob.glob(os.path.join(log_dir, "*.jsonl"))
    
    if not jsonl_files:
        print("❌ No .jsonl files found")
        # Also check for files ending with .jsonl.*
        jsonl_patterns = glob.glob(os.path.join(log_dir, "*.jsonl.*"))
        if jsonl_patterns:
            print(f"   Found files with .jsonl.* pattern: {len(jsonl_patterns)}")
            jsonl_files = jsonl_patterns
    
    if not jsonl_files:
        return None
    
    print(f"✅ Found {len(jsonl_files)} JSONL file(s)")
    
    # Find most recent file by modification time
    most_recent = max(jsonl_files, key=os.path.getmtime)
    file_size = os.path.getsize(most_recent)
    mod_time = datetime.fromtimestamp(os.path.getmtime(most_recent))
    
    print(f"📄 Most recent file: {os.path.basename(most_recent)}")
    print(f"   Size: {file_size:,} bytes")
    print(f"   Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return most_recent

def read_and_parse_jsonl_file(filepath, limit=50):
    """
    Read JSONL file and extract content.text from log entries
    
    Args:
        filepath: Path to JSONL file
        limit: Maximum number of entries to process
    
    Returns:
        List of extracted content.text entries
    """
    print(f"\n📖 Reading JSONL file: {os.path.basename(filepath)}")
    print(f"   Processing up to {limit} most recent entries...")
    
    entries = []
    content_texts = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"   Total lines in file: {len(lines)}")
        
        # Process lines (most recent first if we want reverse)
        lines_to_process = lines[-limit:] if limit else lines
        
        for i, line in enumerate(lines_to_process, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                entry = json.loads(line)
                entries.append(entry)
                
                # Extract content.text from various possible structures
                content_text = None
                
                # Try different possible structures
                if isinstance(entry, dict):
                    # Structure 1: Direct content.text
                    if 'content' in entry and isinstance(entry['content'], dict):
                        content_text = entry['content'].get('text')
                    
                    # Structure 2: Message with text
                    elif 'message' in entry and isinstance(entry['message'], dict):
                        content_text = entry['message'].get('text')
                    
                    # Structure 3: Update with message
                    elif 'update' in entry and isinstance(entry['update'], dict):
                        if 'message' in entry['update']:
                            content_text = entry['update']['message'].get('text')
                    
                    # Structure 4: Direct text field
                    elif 'text' in entry:
                        content_text = entry['text']
                    
                    # Structure 5: Look for any text field in nested structure
                    else:
                        # Recursively search for text field
                        def find_text(obj):
                            if isinstance(obj, dict):
                                if 'text' in obj:
                                    return obj['text']
                                for value in obj.values():
                                    result = find_text(value)
                                    if result:
                                        return result
                            elif isinstance(obj, list):
                                for item in obj:
                                    result = find_text(item)
                                    if result:
                                        return result
                            return None
                        
                        content_text = find_text(entry)
                
                if content_text:
                    # Get timestamp if available
                    timestamp = None
                    if isinstance(entry, dict):
                        timestamp = entry.get('timestamp') or entry.get('time') or entry.get('date')
                    
                    content_texts.append({
                        'line_number': len(lines) - len(lines_to_process) + i,
                        'timestamp': timestamp,
                        'text': content_text[:200]  # Truncate for display
                    })
                    
            except json.JSONDecodeError as e:
                print(f"   ⚠️  Line {i}: JSON decode error: {e}")
                continue
            except Exception as e:
                print(f"   ⚠️  Line {i}: Error: {e}")
                continue
        
        print(f"✅ Successfully parsed {len(entries)} entries")
        print(f"✅ Extracted {len(content_texts)} content.text entries")
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
    
    return content_texts

def display_content_texts(content_texts, max_display=20):
    """Display extracted content.text entries"""
    if not content_texts:
        print("\n📭 No content.text entries found")
        return
    
    print(f"\n{'='*80}")
    print(f"EXTRACTED CONTENT.TEXT ENTRIES (showing {min(max_display, len(content_texts))} of {len(content_texts)})")
    print(f"{'='*80}")
    
    for i, entry in enumerate(content_texts[:max_display], 1):
        print(f"\n[{i}] Line {entry['line_number']}")
        if entry['timestamp']:
            print(f"   Time: {entry['timestamp']}")
        print(f"   Text: {entry['text']}")
    
    # Save to file
    if content_texts:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"extracted_content_texts_{timestamp}.json"
        
        # Include full text in saved file (not truncated)
        full_entries = []
        for entry in content_texts:
            # We need to re-read to get full text
            full_entries.append({
                'line_number': entry['line_number'],
                'timestamp': entry['timestamp'],
                'text': entry['text']  # This is truncated, but okay for now
            })
        
        with open(filename, 'w') as f:
            json.dump(full_entries, f, indent=2)
        
        print(f"\n📄 Full results saved to: {filename}")

def main():
    """Main function"""
    print("=" * 80)
    print("READ JSONL LOGS AND EXTRACT CONTENT.TEXT")
    print("=" * 80)
    
    # Step 1: Load bot config
    bot = load_bot_config()
    if not bot:
        return
    
    # Step 2: Extract log directory from webhook URL
    log_dir = extract_log_directory_from_webhook(bot['webhook_url'])
    if not log_dir:
        print("❌ Could not determine log directory")
        return
    
    # Step 3: Find most recent JSONL file
    jsonl_file = find_most_recent_jsonl_file(log_dir)
    if not jsonl_file:
        print("❌ No JSONL files found")
        return
    
    # Step 4: Read and parse JSONL file
    content_texts = read_and_parse_jsonl_file(jsonl_file, limit=100)
    
    # Step 5: Display results
    display_content_texts(content_texts, max_display=25)
    
    print("\n" + "=" * 80)
    print("✅ JSONL LOG READER COMPLETE")
    print("=" * 80)
    
    print(f"\n📋 Summary:")
    print(f"   Bot: {bot['name']}")
    print(f"   Webhook URL: {bot['webhook_url']}")
    print(f"   Log directory: {log_dir}")
    print(f"   JSONL file: {os.path.basename(jsonl_file)}")
    print(f"   Entries extracted: {len(content_texts)}")
    
    print(f"\n🔧 Tips:")
    print(f"   1. To see more entries, increase the limit in the script")
    print(f"   2. Check the saved JSON file for full results")
    print(f"   3. Look for Telegram message patterns in the extracted text")

if __name__ == "__main__":
    main()