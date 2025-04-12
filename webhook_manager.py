"""
US Code Webhook Manager

This module provides webhook integration for the US Code Browser, allowing:
- Registration of webhook endpoints
- Delivery of update notifications via webhooks
- Management of webhook configurations
- Security features for webhook delivery
"""

import json
import logging
import requests
import hmac
import hashlib
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Thread
from queue import Queue

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f'webhook_manager_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger('webhook_manager')

class WebhookManager:
    """Manages webhook registrations and delivery for US Code updates"""
    
    def __init__(self, data_dir="webhook_data", worker_threads=2):
        """Initialize the webhook manager
        
        Args:
            data_dir (str): Directory to store webhook data
            worker_threads (int): Number of worker threads for webhook delivery
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.webhooks_dir = self.data_dir / "webhooks"
        self.delivery_dir = self.data_dir / "delivery"
        self.logs_dir = self.data_dir / "logs"
        
        self.webhooks_dir.mkdir(exist_ok=True)
        self.delivery_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
        
        # Set up delivery queue and workers
        self.delivery_queue = Queue()
        self.workers = []
        
        # Start worker threads
        for i in range(worker_threads):
            worker = Thread(target=self._delivery_worker, daemon=True)
            worker.start()
            self.workers.append(worker)
    
    def _load_config(self):
        """Load configuration from config file"""
        config_file = self.data_dir / "webhook_config.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading webhook config: {e}")
        
        # Default configuration
        default_config = {
            "delivery": {
                "max_retries": 3,
                "retry_delay_seconds": 60,
                "timeout_seconds": 10,
                "max_payload_size_kb": 512
            },
            "security": {
                "sign_payloads": True,
                "signature_header": "X-USCode-Signature",
                "signature_algorithm": "sha256"
            },
            "rate_limiting": {
                "enabled": True,
                "max_per_minute": 60,
                "max_per_hour": 1000
            }
        }
        
        # Save default configuration
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def save_config(self):
        """Save configuration to config file"""
        config_file = self.data_dir / "webhook_config.json"
        
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Webhook configuration saved")
        except Exception as e:
            logger.error(f"Error saving webhook config: {e}")
    
    def register_webhook(self, url, description=None, events=None, secret=None, format="json", headers=None):
        """Register a new webhook
        
        Args:
            url (str): The URL to send webhook payloads to
            description (str, optional): Description of the webhook
            events (list, optional): List of events to subscribe to (default: all)
            secret (str, optional): Secret for signing payloads
            format (str, optional): Payload format (json or xml)
            headers (dict, optional): Additional headers to send
            
        Returns:
            str: Webhook ID if successful, None otherwise
        """
        if not url or not url.startswith(('http://', 'https://')):
            logger.error(f"Invalid webhook URL: {url}")
            return None
        
        # Generate a unique ID for this webhook
        webhook_id = str(uuid.uuid4())
        
        # Create webhook configuration
        webhook = {
            "id": webhook_id,
            "url": url,
            "description": description or f"Webhook registered on {datetime.now().isoformat()}",
            "events": events or ["update.released", "update.processed", "update.error"],
            "secret": secret or self._generate_secret(),
            "format": format.lower(),
            "headers": headers or {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "active": True,
            "stats": {
                "total_deliveries": 0,
                "successful_deliveries": 0,
                "failed_deliveries": 0,
                "last_delivery_at": None,
                "last_delivery_status": None
            }
        }
        
        # Save webhook configuration
        webhook_file = self.webhooks_dir / f"{webhook_id}.json"
        
        try:
            with open(webhook_file, 'w') as f:
                json.dump(webhook, f, indent=2)
            logger.info(f"Webhook registered: {webhook_id} for {url}")
            return webhook_id
        except Exception as e:
            logger.error(f"Error registering webhook: {e}")
            return None
    
    def update_webhook(self, webhook_id, **kwargs):
        """Update an existing webhook
        
        Args:
            webhook_id (str): The ID of the webhook to update
            **kwargs: Fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        webhook_file = self.webhooks_dir / f"{webhook_id}.json"
        
        if not webhook_file.exists():
            logger.error(f"Webhook not found: {webhook_id}")
            return False
        
        try:
            # Load existing webhook
            with open(webhook_file, 'r') as f:
                webhook = json.load(f)
            
            # Update fields
            for key, value in kwargs.items():
                if key in webhook and key not in ['id', 'created_at', 'stats']:
                    webhook[key] = value
            
            # Update timestamp
            webhook['updated_at'] = datetime.now().isoformat()
            
            # Save updated webhook
            with open(webhook_file, 'w') as f:
                json.dump(webhook, f, indent=2)
            
            logger.info(f"Webhook updated: {webhook_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating webhook {webhook_id}: {e}")
            return False
    
    def delete_webhook(self, webhook_id):
        """Delete a webhook
        
        Args:
            webhook_id (str): The ID of the webhook to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        webhook_file = self.webhooks_dir / f"{webhook_id}.json"
        
        if not webhook_file.exists():
            logger.error(f"Webhook not found: {webhook_id}")
            return False
        
        try:
            # Delete the webhook file
            webhook_file.unlink()
            logger.info(f"Webhook deleted: {webhook_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting webhook {webhook_id}: {e}")
            return False
    
    def get_webhook(self, webhook_id):
        """Get webhook details
        
        Args:
            webhook_id (str): The ID of the webhook
            
        Returns:
            dict: Webhook details or None if not found
        """
        webhook_file = self.webhooks_dir / f"{webhook_id}.json"
        
        if not webhook_file.exists():
            logger.error(f"Webhook not found: {webhook_id}")
            return None
        
        try:
            with open(webhook_file, 'r') as f:
                webhook = json.load(f)
            
            # Remove secret from the returned data for security
            if 'secret' in webhook:
                webhook['secret'] = '••••••••'
            
            return webhook
        except Exception as e:
            logger.error(f"Error getting webhook {webhook_id}: {e}")
            return None
    
    def list_webhooks(self, active_only=False):
        """List all registered webhooks
        
        Args:
            active_only (bool): Only return active webhooks
            
        Returns:
            list: List of webhook details
        """
        webhooks = []
        
        try:
            webhook_files = list(self.webhooks_dir.glob("*.json"))
            
            for file in webhook_files:
                try:
                    with open(file, 'r') as f:
                        webhook = json.load(f)
                    
                    # Filter by active status if requested
                    if active_only and not webhook.get('active', True):
                        continue
                    
                    # Remove secret from the returned data for security
                    if 'secret' in webhook:
                        webhook['secret'] = '••••••••'
                    
                    webhooks.append(webhook)
                except Exception as e:
                    logger.error(f"Error loading webhook file {file}: {e}")
            
            return webhooks
        except Exception as e:
            logger.error(f"Error listing webhooks: {e}")
            return []
    
    def trigger_webhooks(self, event, payload, filter_ids=None):
        """Trigger webhooks for a specific event
        
        Args:
            event (str): The event name
            payload (dict): The payload to send
            filter_ids (list, optional): Only trigger specific webhook IDs
            
        Returns:
            int: Number of webhooks triggered
        """
        count = 0
        
        try:
            # Get all webhooks
            webhook_files = list(self.webhooks_dir.glob("*.json"))
            
            for file in webhook_files:
                try:
                    with open(file, 'r') as f:
                        webhook = json.load(f)
                    
                    # Skip if webhook is not active
                    if not webhook.get('active', True):
                        continue
                    
                    # Skip if this webhook ID is not in the filter list
                    if filter_ids and webhook['id'] not in filter_ids:
                        continue
                    
                    # Skip if this webhook doesn't subscribe to this event
                    if event not in webhook.get('events', []):
                        continue
                    
                    # Queue the delivery
                    delivery_id = str(uuid.uuid4())
                    delivery = {
                        'id': delivery_id,
                        'webhook_id': webhook['id'],
                        'event': event,
                        'payload': payload,
                        'created_at': datetime.now().isoformat(),
                        'attempts': 0,
                        'max_attempts': self.config['delivery']['max_retries']
                    }
                    
                    # Save delivery record
                    delivery_file = self.delivery_dir / f"{delivery_id}.json"
                    with open(delivery_file, 'w') as f:
                        json.dump(delivery, f, indent=2)
                    
                    # Queue for delivery
                    self.delivery_queue.put((delivery_id, webhook['id']))
                    count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing webhook file {file}: {e}")
            
            logger.info(f"Triggered {count} webhooks for event {event}")
            return count
        except Exception as e:
            logger.error(f"Error triggering webhooks: {e}")
            return 0
    
    def _delivery_worker(self):
        """Worker thread for webhook delivery"""
        while True:
            try:
                # Get a delivery from the queue
                delivery_id, webhook_id = self.delivery_queue.get()
                
                # Process the delivery
                self._process_delivery(delivery_id, webhook_id)
                
                # Mark the task as done
                self.delivery_queue.task_done()
            except Exception as e:
                logger.error(f"Error in webhook delivery worker: {e}")
    
    def _process_delivery(self, delivery_id, webhook_id):
        """Process a webhook delivery
        
        Args:
            delivery_id (str): The ID of the delivery
            webhook_id (str): The ID of the webhook
        """
        delivery_file = self.delivery_dir / f"{delivery_id}.json"
        webhook_file = self.webhooks_dir / f"{webhook_id}.json"
        
        if not delivery_file.exists() or not webhook_file.exists():
            logger.error(f"Delivery {delivery_id} or webhook {webhook_id} not found")
            return
        
        try:
            # Load delivery and webhook
            with open(delivery_file, 'r') as f:
                delivery = json.load(f)
            
            with open(webhook_file, 'r') as f:
                webhook = json.load(f)
            
            # Check if we've exceeded max attempts
            if delivery['attempts'] >= delivery['max_attempts']:
                logger.warning(f"Delivery {delivery_id} exceeded max attempts")
                self._update_delivery_status(delivery_id, 'failed', "Exceeded max attempts")
                self._update_webhook_stats(webhook_id, False)
                return
            
            # Increment attempt counter
            delivery['attempts'] += 1
            
            # Format the payload
            formatted_payload = self._format_payload(delivery['payload'], webhook['format'])
            
            # Prepare headers
            headers = {
                'Content-Type': 'application/json' if webhook['format'] == 'json' else 'application/xml',
                'User-Agent': 'USCodeBrowser-Webhook/1.0',
                'X-USCode-Event': delivery['event'],
                'X-USCode-Delivery': delivery_id
            }
            
            # Add custom headers
            if webhook.get('headers'):
                headers.update(webhook['headers'])
            
            # Sign the payload if enabled
            if self.config['security']['sign_payloads'] and webhook.get('secret'):
                signature = self._sign_payload(formatted_payload, webhook['secret'])
                headers[self.config['security']['signature_header']] = signature
            
            # Send the webhook
            response = requests.post(
                webhook['url'],
                data=formatted_payload,
                headers=headers,
                timeout=self.config['delivery']['timeout_seconds']
            )
            
            # Check response
            success = 200 <= response.status_code < 300
            
            # Update delivery status
            status_message = f"HTTP {response.status_code}" if success else f"HTTP {response.status_code}: {response.text[:100]}"
            self._update_delivery_status(delivery_id, 'delivered' if success else 'failed', status_message)
            
            # Update webhook stats
            self._update_webhook_stats(webhook_id, success)
            
            # Log the result
            if success:
                logger.info(f"Webhook {webhook_id} delivered successfully: {delivery_id}")
            else:
                logger.warning(f"Webhook {webhook_id} delivery failed: {delivery_id} - {status_message}")
                
                # Retry if needed
                if delivery['attempts'] < delivery['max_attempts']:
                    # Save updated delivery
                    with open(delivery_file, 'w') as f:
                        json.dump(delivery, f, indent=2)
                    
                    # Re-queue after delay
                    retry_delay = self.config['delivery']['retry_delay_seconds']
                    logger.info(f"Requeuing delivery {delivery_id} in {retry_delay} seconds")
                    
                    def requeue():
                        time.sleep(retry_delay)
                        self.delivery_queue.put((delivery_id, webhook_id))
                    
                    Thread(target=requeue).start()
            
        except Exception as e:
            logger.error(f"Error processing delivery {delivery_id}: {e}")
            self._update_delivery_status(delivery_id, 'failed', str(e))
            self._update_webhook_stats(webhook_id, False)
    
    def _update_delivery_status(self, delivery_id, status, message=None):
        """Update the status of a delivery
        
        Args:
            delivery_id (str): The ID of the delivery
            status (str): The new status
            message (str, optional): Status message
        """
        delivery_file = self.delivery_dir / f"{delivery_id}.json"
        
        if not delivery_file.exists():
            logger.error(f"Delivery {delivery_id} not found")
            return
        
        try:
            # Load delivery
            with open(delivery_file, 'r') as f:
                delivery = json.load(f)
            
            # Update status
            delivery['status'] = status
            delivery['status_message'] = message
            delivery['updated_at'] = datetime.now().isoformat()
            
            # Save updated delivery
            with open(delivery_file, 'w') as f:
                json.dump(delivery, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating delivery status for {delivery_id}: {e}")
    
    def _update_webhook_stats(self, webhook_id, success):
        """Update the stats for a webhook
        
        Args:
            webhook_id (str): The ID of the webhook
            success (bool): Whether the delivery was successful
        """
        webhook_file = self.webhooks_dir / f"{webhook_id}.json"
        
        if not webhook_file.exists():
            logger.error(f"Webhook {webhook_id} not found")
            return
        
        try:
            # Load webhook
            with open(webhook_file, 'r') as f:
                webhook = json.load(f)
            
            # Initialize stats if needed
            if 'stats' not in webhook:
                webhook['stats'] = {
                    'total_deliveries': 0,
                    'successful_deliveries': 0,
                    'failed_deliveries': 0,
                    'last_delivery_at': None,
                    'last_delivery_status': None
                }
            
            # Update stats
            webhook['stats']['total_deliveries'] += 1
            if success:
                webhook['stats']['successful_deliveries'] += 1
            else:
                webhook['stats']['failed_deliveries'] += 1
            
            webhook['stats']['last_delivery_at'] = datetime.now().isoformat()
            webhook['stats']['last_delivery_status'] = 'success' if success else 'failed'
            
            # Save updated webhook
            with open(webhook_file, 'w') as f:
                json.dump(webhook, f, indent=2)
        except Exception as e:
            logger.error(f"Error updating webhook stats for {webhook_id}: {e}")
    
    def _format_payload(self, payload, format_type):
        """Format the payload according to the specified format
        
        Args:
            payload (dict): The payload to format
            format_type (str): The format type (json or xml)
            
        Returns:
            str: Formatted payload
        """
        if format_type == 'json':
            return json.dumps(payload)
        elif format_type == 'xml':
            # Simple XML conversion (for more complex needs, use a proper XML library)
            xml = ['<?xml version="1.0" encoding="UTF-8"?>']
            xml.append('<webhook-payload>')
            
            def dict_to_xml(d, parent_tag=None):
                result = []
                for key, value in d.items():
                    if isinstance(value, dict):
                        result.append(f'<{key}>')
                        result.append(dict_to_xml(value, key))
                        result.append(f'</{key}>')
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                result.append(f'<{key}>')
                                result.append(dict_to_xml(item, key))
                                result.append(f'</{key}>')
                            else:
                                result.append(f'<{key}>{item}</{key}>')
                    else:
                        result.append(f'<{key}>{value}</{key}>')
                return '\n'.join(result)
            
            xml.append(dict_to_xml(payload))
            xml.append('</webhook-payload>')
            return '\n'.join(xml)
        else:
            logger.warning(f"Unsupported format: {format_type}, defaulting to JSON")
            return json.dumps(payload)
    
    def _sign_payload(self, payload, secret):
        """Sign the payload using the webhook secret
        
        Args:
            payload (str): The payload to sign
            secret (str): The secret to use for signing
            
        Returns:
            str: Signature
        """
        algorithm = self.config['security']['signature_algorithm']
        
        if algorithm == 'sha256':
            signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
        elif algorithm == 'sha1':
            signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha1
            ).hexdigest()
        else:
            logger.warning(f"Unsupported signature algorithm: {algorithm}, defaulting to sha256")
            signature = hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
        
        return f"{algorithm}={signature}"
    
    def _generate_secret(self):
        """Generate a random secret for webhook signing
        
        Returns:
            str: Random secret
        """
        return uuid.uuid4().hex + uuid.uuid4().hex

# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='US Code Webhook Manager')
    parser.add_argument('--register', action='store_true', help='Register a new webhook')
    parser.add_argument('--list', action='store_true', help='List all webhooks')
    parser.add_argument('--update', metavar='ID', help='Update a webhook')
    parser.add_argument('--delete', metavar='ID', help='Delete a webhook')
    parser.add_argument('--trigger', action='store_true', help='Trigger webhooks for testing')
    parser.add_argument('--url', help='Webhook URL (for --register)')
    parser.add_argument('--events', help='Comma-separated list of events (for --register)')
    parser.add_argument('--description', help='Webhook description (for --register)')
    parser.add_argument('--format', choices=['json', 'xml'], default='json', help='Payload format (for --register)')
    
    args = parser.parse_args()
    
    manager = WebhookManager()
    
    if args.register:
        if not args.url:
            print("Error: URL is required for webhook registration")
            exit(1)
        
        events = args.events.split(',') if args.events else None
        webhook_id = manager.register_webhook(
            url=args.url,
            description=args.description,
            events=events,
            format=args.format
        )
        
        if webhook_id:
            print(f"Webhook registered successfully with ID: {webhook_id}")
        else:
            print("Failed to register webhook")
    
    elif args.list:
        webhooks = manager.list_webhooks()
        if webhooks:
            print(f"Found {len(webhooks)} webhooks:")
            for webhook in webhooks:
                print(f"ID: {webhook['id']}")
                print(f"URL: {webhook['url']}")
                print(f"Description: {webhook['description']}")
                print(f"Events: {', '.join(webhook['events'])}")
                print(f"Format: {webhook['format']}")
                print(f"Active: {webhook['active']}")
                print(f"Created: {webhook['created_at']}")
                print("Stats:")
                stats = webhook.get('stats', {})
                print(f"  Total deliveries: {stats.get('total_deliveries', 0)}")
                print(f"  Successful: {stats.get('successful_deliveries', 0)}")
                print(f"  Failed: {stats.get('failed_deliveries', 0)}")
                print(f"  Last delivery: {stats.get('last_delivery_at', 'Never')}")
                print(f"  Last status: {stats.get('last_delivery_status', 'N/A')}")
                print("-" * 50)
        else:
            print("No webhooks found")
    
    elif args.update:
        # Simple update to toggle active status
        webhook = manager.get_webhook(args.update)
        if webhook:
            active = not webhook.get('active', True)
            success = manager.update_webhook(args.update, active=active)
            if success:
                print(f"Webhook {args.update} {'activated' if active else 'deactivated'}")
            else:
                print(f"Failed to update webhook {args.update}")
        else:
            print(f"Webhook {args.update} not found")
    
    elif args.delete:
        success = manager.delete_webhook(args.delete)
        if success:
            print(f"Webhook {args.delete} deleted")
        else:
            print(f"Failed to delete webhook {args.delete}")
    
    elif args.trigger:
        # Trigger a test event
        count = manager.trigger_webhooks("test.event", {
            "message": "This is a test webhook event",
            "timestamp": datetime.now().isoformat(),
            "test": True
        })
        
        if count > 0:
            print(f"Triggered {count} webhooks")
        else:
            print("No webhooks were triggered")
    
    else:
        parser.print_help()
