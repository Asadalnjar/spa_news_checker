#!/usr/bin/env python3
"""
Health check endpoint for cloud deployment monitoring.
Optional HTTP server for health checks and status monitoring.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading


class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check requests."""
    
    def do_GET(self):
        """Handle GET requests for health checks."""
        if self.path == '/health':
            self.send_health_response()
        elif self.path == '/status':
            self.send_status_response()
        else:
            self.send_response(404)
            self.end_headers()
    
    def send_health_response(self):
        """Send basic health check response."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'spa-news-monitor'
        }
        
        self.wfile.write(json.dumps(response).encode())
    
    def send_status_response(self):
        """Send detailed status response."""
        try:
            db_path = os.getenv('DATABASE_PATH', 'news_monitor.db')
            
            # Check database
            db_status = self.check_database(db_path)
            
            # Check recent activity
            recent_activity = self.check_recent_activity(db_path)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'spa-news-monitor',
                'database': db_status,
                'recent_activity': recent_activity,
                'environment': {
                    'openai_configured': bool(os.getenv('OPENAI_API_KEY')),
                    'email_configured': bool(os.getenv('EMAIL_USERNAME')),
                    'target_url': os.getenv('TARGET_URL', 'Not set'),
                    'check_interval': os.getenv('CHECK_INTERVAL_MINUTES', '20')
                }
            }
            
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            error_response = {
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            
            self.wfile.write(json.dumps(error_response).encode())
    
    def check_database(self, db_path):
        """Check database status."""
        try:
            if not os.path.exists(db_path):
                return {'status': 'missing', 'message': 'Database file not found'}
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed_articles'")
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                conn.close()
                return {'status': 'error', 'message': 'Table not found'}
            
            # Count processed articles
            cursor.execute("SELECT COUNT(*) FROM processed_articles")
            count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'status': 'healthy',
                'total_articles': count,
                'file_size': os.path.getsize(db_path)
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def check_recent_activity(self, db_path):
        """Check for recent monitoring activity."""
        try:
            if not os.path.exists(db_path):
                return {'status': 'no_data', 'message': 'No database found'}
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check for articles processed in last 24 hours
            yesterday = datetime.now() - timedelta(hours=24)
            cursor.execute(
                "SELECT COUNT(*) FROM processed_articles WHERE processed_at > ?",
                (yesterday.isoformat(),)
            )
            recent_count = cursor.fetchone()[0]
            
            # Get last processed article
            cursor.execute(
                "SELECT url, processed_at, grammar_status FROM processed_articles ORDER BY processed_at DESC LIMIT 1"
            )
            last_article = cursor.fetchone()
            
            conn.close()
            
            result = {
                'articles_last_24h': recent_count,
                'last_article': None
            }
            
            if last_article:
                result['last_article'] = {
                    'url': last_article[0],
                    'processed_at': last_article[1],
                    'status': last_article[2]
                }
            
            return result
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def log_message(self, format, *args):
        """Override to suppress HTTP logs."""
        pass


def start_health_server(port=8080):
    """Start the health check server."""
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        print(f"Health check server started on port {port}")
        print(f"Health endpoint: http://localhost:{port}/health")
        print(f"Status endpoint: http://localhost:{port}/status")
        server.serve_forever()
    except Exception as e:
        print(f"Failed to start health server: {e}")


def run_health_server_background(port=8080):
    """Run health server in background thread."""
    health_thread = threading.Thread(target=start_health_server, args=(port,), daemon=True)
    health_thread.start()
    return health_thread


if __name__ == "__main__":
    # Run standalone health server
    port = int(os.getenv('PORT', 8080))
    start_health_server(port)