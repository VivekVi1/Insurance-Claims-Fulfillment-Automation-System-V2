#!/usr/bin/env python3
"""
AI Insurance Claim Processing System - Startup Script

This script starts all the microservices and the main monitoring system.
Use this for development and testing purposes.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

# Global state for managing processes
PROCESSES = []

# Service configuration
SERVICES = [
    {
        'name': 'User Validator API',
        'script': 'apis/user_validator.py',
        'port': 8000,
        'health_endpoint': 'http://localhost:8000/'
    },
    {
        'name': 'Mail Service API',
        'script': 'apis/mail_service.py', 
        'port': 8001,
        'health_endpoint': 'http://localhost:8001/'
    },
    {
        'name': 'Fulfillment API',
        'script': 'apis/fulfillment_api.py',
        'port': 8002,
        'health_endpoint': 'http://localhost:8002/'
    }
]

def check_prerequisites():
    """Check if all required files exist"""
    print("🔍 Checking prerequisites...")
    
    # Check if .env file exists
    if not Path('.env').exists():
        print("❌ .env file not found!")
        print("📝 Please create a .env file using the template in setup_guide.md")
        return False
        
    # Check if all API scripts exist
    for service in SERVICES:
        script_path = Path(service['script'])
        if not script_path.exists():
            print(f"❌ {service['script']} not found!")
            return False
            
    # Check if main scripts exist
    required_scripts = ['mail_monitor.py', 'fulfillment_processor.py', 's3_uploader.py']
    for script in required_scripts:
        if not Path(script).exists():
            print(f"❌ {script} not found!")
            return False
            
    print("✅ All prerequisites met!")
    return True

def start_service(service):
    """Start a single service"""
    global PROCESSES
    print(f"🚀 Starting {service['name']} on port {service['port']}...")
    
    try:
        process = subprocess.Popen(
            [sys.executable, service['script']],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        PROCESSES.append({
            'process': process,
            'name': service['name'],
            'port': service['port']
        })
        
        # Give the service a moment to start
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is None:
            print(f"✅ {service['name']} started successfully")
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ {service['name']} failed to start")
            print(f"Error: {stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start {service['name']}: {e}")
        return False

def start_all_services():
    """Start all API services"""
    print("\n🔄 Starting API services...")
    
    success_count = 0
    for service in SERVICES:
        if start_service(service):
            success_count += 1
        else:
            print(f"⚠️  Failed to start {service['name']}")
            
    print(f"\n📊 Started {success_count}/{len(SERVICES)} services")
    
    if success_count == len(SERVICES):
        print("✅ All API services started successfully!")
        return True
    else:
        print("⚠️  Some services failed to start. Check the errors above.")
        return False

def start_mail_monitor():
    """Start the main mail monitoring system"""
    global PROCESSES
    print("\n🚀 Starting Mail Monitor (main system)...")
    
    try:
        process = subprocess.Popen(
            [sys.executable, 'mail_monitor.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        PROCESSES.append({
            'process': process,
            'name': 'Mail Monitor',
            'port': 'N/A'
        })
        
        print("✅ Mail Monitor started!")
        print("📧 System is now monitoring emails...")
        print("\n" + "="*60)
        print("🎯 SYSTEM READY - AI Insurance Claim Processing Active")
        print("="*60)
        
        # Stream output from mail monitor
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(line.rstrip())
                    
        except KeyboardInterrupt:
            print("\n🛑 Received interrupt signal...")
            
    except Exception as e:
        print(f"❌ Failed to start Mail Monitor: {e}")
        return False

def stop_all_services():
    """Stop all running services"""
    global PROCESSES
    print("\n🛑 Stopping all services...")
    
    for proc_info in PROCESSES:
        try:
            process = proc_info['process']
            name = proc_info['name']
            
            if process.poll() is None:  # Process is still running
                print(f"🔄 Stopping {name}...")
                process.terminate()
                
                # Wait up to 5 seconds for graceful shutdown
                try:
                    process.wait(timeout=5)
                    print(f"✅ {name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    print(f"⚠️  Force killing {name}...")
                    process.kill()
                    process.wait()
                    print(f"🔥 {name} force stopped")
                    
        except Exception as e:
            print(f"❌ Error stopping {proc_info['name']}: {e}")
            
    print("🔒 All services stopped")

def show_status():
    """Show status of all services"""
    print("\n📊 Service Status:")
    print("-" * 50)
    
    for service in SERVICES:
        print(f"🌐 {service['name']:<20} Port {service['port']:<5} {service['health_endpoint']}")
        
    print(f"📧 Mail Monitor          Main System")
    print("-" * 50)

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        print(f"\n🔔 Received signal {signum}")
        stop_all_services()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def run():
    """Main execution method"""
    print("🏥 AI Insurance Claim Processing System - Startup")
    print("=" * 55)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please fix the issues above.")
        sys.exit(1)
        
    # Setup signal handlers
    setup_signal_handlers()
    
    # Start API services
    if not start_all_services():
        print("\n❌ Failed to start all API services.")
        print("💡 Try starting services individually to debug issues.")
        stop_all_services()
        sys.exit(1)
        
    # Show service status
    show_status()
    
    # Start mail monitor (this will run indefinitely)
    print("\n⏰ Waiting 5 seconds for all services to stabilize...")
    time.sleep(5)
    
    try:
        start_mail_monitor()
    except KeyboardInterrupt:
        pass
    finally:
        stop_all_services()

def main():
    """Main entry point"""
    try:
        run()
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 