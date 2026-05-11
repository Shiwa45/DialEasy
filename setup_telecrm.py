#!/usr/bin/env python
"""
TeleCRM Setup Script
This script sets up the initial data for the TeleCRM application
Run this from the project root directory (where manage.py is located)
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'telecrm_project.settings')

try:
    django.setup()
except Exception as e:
    print(f"❌ Error setting up Django: {e}")
    print("Make sure you're running this script from the project root directory (where manage.py is located)")
    sys.exit(1)

from django.contrib.auth.models import User
from django.db import transaction
from leads.models import Lead, CallLog, FollowUp

def create_sample_data():
    """Create sample data for testing"""
    
    print("🚀 Setting up TeleCRM with sample data...")
    
    try:
        with transaction.atomic():
            # Create superuser if it doesn't exist
            if not User.objects.filter(username='admin').exists():
                admin_user = User.objects.create_superuser(
                    'admin', 
                    'admin@telecrm.com', 
                    'admin123',
                    first_name='Admin',
                    last_name='User'
                )
                print("✅ Created admin user: admin / admin123")
            else:
                print("ℹ️  Admin user already exists")
            
            # Create sample agents
            agents_data = [
                {
                    'username': 'agent1',
                    'email': 'agent1@telecrm.com',
                    'password': 'password123',
                    'first_name': 'John',
                    'last_name': 'Doe'
                },
                {
                    'username': 'agent2',
                    'email': 'agent2@telecrm.com',
                    'password': 'password123',
                    'first_name': 'Jane',
                    'last_name': 'Smith'
                },
                {
                    'username': 'agent3',
                    'email': 'agent3@telecrm.com',
                    'password': 'password123',
                    'first_name': 'Mike',
                    'last_name': 'Johnson'
                }
            ]
            
            created_agents = []
            for agent_data in agents_data:
                if not User.objects.filter(username=agent_data['username']).exists():
                    agent = User.objects.create_user(
                        username=agent_data['username'],
                        email=agent_data['email'],
                        password=agent_data['password'],
                        first_name=agent_data['first_name'],
                        last_name=agent_data['last_name'],
                        is_staff=False
                    )
                    created_agents.append(agent)
                    print(f"✅ Created agent: {agent_data['username']} / password123")
                else:
                    agent = User.objects.get(username=agent_data['username'])
                    created_agents.append(agent)
                    print(f"ℹ️  Agent {agent_data['username']} already exists")
            
            # Create sample leads only if none exist
            if Lead.objects.count() == 0:
                sample_leads = [
                    {
                        'name': 'Alice Williams',
                        'phone': '+1234567890',
                        'email': 'alice@example.com',
                        'company': 'Tech Solutions Inc',
                        'source': 'Website',
                        'status': 'new'
                    },
                    {
                        'name': 'Bob Brown',
                        'phone': '+1234567891',
                        'email': 'bob@company.com',
                        'company': 'Marketing Corp',
                        'source': 'Referral',
                        'status': 'contacted'
                    },
                    {
                        'name': 'Carol Davis',
                        'phone': '+1234567892',
                        'email': 'carol@business.com',
                        'company': 'Sales Dynamics',
                        'source': 'Social Media',
                        'status': 'interested'
                    },
                    {
                        'name': 'David Miller',
                        'phone': '+1234567893',
                        'email': 'david@enterprise.com',
                        'company': 'Enterprise Solutions',
                        'source': 'Cold Call',
                        'status': 'new'
                    },
                    {
                        'name': 'Emma Wilson',
                        'phone': '+1234567894',
                        'email': 'emma@startup.com',
                        'company': 'Startup Innovations',
                        'source': 'LinkedIn',
                        'status': 'callback'
                    },
                    {
                        'name': 'Frank Taylor',
                        'phone': '+1234567895',
                        'email': 'frank@consulting.com',
                        'company': 'Taylor Consulting',
                        'source': 'Website',
                        'status': 'new'
                    },
                    {
                        'name': 'Grace Lee',
                        'phone': '+1234567896',
                        'email': 'grace@design.com',
                        'company': 'Creative Designs',
                        'source': 'Email Campaign',
                        'status': 'interested'
                    },
                    {
                        'name': 'Henry Anderson',
                        'phone': '+1234567897',
                        'email': 'henry@logistics.com',
                        'company': 'Logistics Pro',
                        'source': 'Trade Show',
                        'status': 'not_interested'
                    },
                    {
                        'name': 'Ivy Chen',
                        'phone': '+1234567898',
                        'email': 'ivy@fintech.com',
                        'company': 'FinTech Innovations',
                        'source': 'Referral',
                        'status': 'converted'
                    },
                    {
                        'name': 'Jack Robinson',
                        'phone': '+1234567899',
                        'email': 'jack@retail.com',
                        'company': 'Retail Masters',
                        'source': 'Google Ads',
                        'status': 'contacted'
                    }
                ]
                
                # Assign leads to agents
                for i, lead_data in enumerate(sample_leads):
                    # Assign to agents in round-robin fashion
                    if created_agents:
                        agent = created_agents[i % len(created_agents)]
                        lead_data['assigned_agent'] = agent
                    
                    lead = Lead.objects.create(**lead_data)
                    print(f"✅ Created lead: {lead.name}" + (f" (assigned to {agent.username})" if created_agents else ""))
                
                print(f"✅ Created {len(sample_leads)} sample leads")
            else:
                print("ℹ️  Leads already exist, skipping sample lead creation")
            
            print("\n🎉 TeleCRM setup completed successfully!")
            print("\n📋 Login Credentials:")
            print("Admin Panel: http://localhost:8000/admin/")
            print("  └─ Username: admin")
            print("  └─ Password: admin123")
            print("\nCRM Dashboard: http://localhost:8000/")
            print("  └─ Username: admin")
            print("  └─ Password: admin123")
            print("\nAPI Endpoints: http://localhost:8000/api/")
            print("  └─ Agent Login: agent1 / password123")
            print("  └─ Agent Login: agent2 / password123")
            print("  └─ Agent Login: agent3 / password123")
            
            print("\n📱 Mobile App API Test:")
            print("POST /api/auth/login/ with:")
            print('{"username": "agent1", "password": "password123"}')
            
    except Exception as e:
        print(f"❌ Error during setup: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main setup function"""
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths
    
    # Check if manage.py exists
    if not os.path.exists('manage.py'):
        print("❌ manage.py not found. Make sure you're running this script from the Django project root directory.")
        print("   Expected directory structure:")
        print("   telecrm_project/")
        print("   ├── manage.py")
        print("   ├── setup_telecrm.py")
        print("   ├── telecrm_project/")
        print("   ├── leads/")
        print("   ├── agents/")
        print("   └── api/")
        sys.exit(1)
    
    create_sample_data()

if __name__ == '__main__':
    main()
    """Create sample data for testing"""
    
    print("🚀 Setting up TeleCRM with sample data...")
    
    try:
        with transaction.atomic():
            # Create superuser if it doesn't exist
            if not User.objects.filter(username='admin').exists():
                admin_user = User.objects.create_superuser(
                    'admin', 
                    'admin@telecrm.com', 
                    'admin123',
                    first_name='Admin',
                    last_name='User'
                )
                print("✅ Created admin user: admin / admin123")
            else:
                print("ℹ️  Admin user already exists")
            
            # Create sample agents
            agents_data = [
                {
                    'username': 'agent1',
                    'email': 'agent1@telecrm.com',
                    'password': 'password123',
                    'first_name': 'John',
                    'last_name': 'Doe'
                },
                {
                    'username': 'agent2',
                    'email': 'agent2@telecrm.com',
                    'password': 'password123',
                    'first_name': 'Jane',
                    'last_name': 'Smith'
                },
                {
                    'username': 'agent3',
                    'email': 'agent3@telecrm.com',
                    'password': 'password123',
                    'first_name': 'Mike',
                    'last_name': 'Johnson'
                }
            ]
            
            created_agents = []
            for agent_data in agents_data:
                if not User.objects.filter(username=agent_data['username']).exists():
                    agent = User.objects.create_user(
                        username=agent_data['username'],
                        email=agent_data['email'],
                        password=agent_data['password'],
                        first_name=agent_data['first_name'],
                        last_name=agent_data['last_name'],
                        is_staff=False
                    )
                    created_agents.append(agent)
                    print(f"✅ Created agent: {agent_data['username']} / password123")
                else:
                    agent = User.objects.get(username=agent_data['username'])
                    created_agents.append(agent)
                    print(f"ℹ️  Agent {agent_data['username']} already exists")
            
            # Create sample leads only if none exist
            if Lead.objects.count() == 0:
                sample_leads = [
                    {
                        'name': 'Alice Williams',
                        'phone': '+1234567890',
                        'email': 'alice@example.com',
                        'company': 'Tech Solutions Inc',
                        'source': 'Website',
                        'status': 'new'
                    },
                    {
                        'name': 'Bob Brown',
                        'phone': '+1234567891',
                        'email': 'bob@company.com',
                        'company': 'Marketing Corp',
                        'source': 'Referral',
                        'status': 'contacted'
                    },
                    {
                        'name': 'Carol Davis',
                        'phone': '+1234567892',
                        'email': 'carol@business.com',
                        'company': 'Sales Dynamics',
                        'source': 'Social Media',
                        'status': 'interested'
                    },
                    {
                        'name': 'David Miller',
                        'phone': '+1234567893',
                        'email': 'david@enterprise.com',
                        'company': 'Enterprise Solutions',
                        'source': 'Cold Call',
                        'status': 'new'
                    },
                    {
                        'name': 'Emma Wilson',
                        'phone': '+1234567894',
                        'email': 'emma@startup.com',
                        'company': 'Startup Innovations',
                        'source': 'LinkedIn',
                        'status': 'callback'
                    },
                    {
                        'name': 'Frank Taylor',
                        'phone': '+1234567895',
                        'email': 'frank@consulting.com',
                        'company': 'Taylor Consulting',
                        'source': 'Website',
                        'status': 'new'
                    },
                    {
                        'name': 'Grace Lee',
                        'phone': '+1234567896',
                        'email': 'grace@design.com',
                        'company': 'Creative Designs',
                        'source': 'Email Campaign',
                        'status': 'interested'
                    },
                    {
                        'name': 'Henry Anderson',
                        'phone': '+1234567897',
                        'email': 'henry@logistics.com',
                        'company': 'Logistics Pro',
                        'source': 'Trade Show',
                        'status': 'not_interested'
                    },
                    {
                        'name': 'Ivy Chen',
                        'phone': '+1234567898',
                        'email': 'ivy@fintech.com',
                        'company': 'FinTech Innovations',
                        'source': 'Referral',
                        'status': 'converted'
                    },
                    {
                        'name': 'Jack Robinson',
                        'phone': '+1234567899',
                        'email': 'jack@retail.com',
                        'company': 'Retail Masters',
                        'source': 'Google Ads',
                        'status': 'contacted'
                    }
                ]
                
                # Assign leads to agents
                for i, lead_data in enumerate(sample_leads):
                    # Assign to agents in round-robin fashion
                    agent = created_agents[i % len(created_agents)]
                    lead_data['assigned_agent'] = agent
                    
                    lead = Lead.objects.create(**lead_data)
                    print(f"✅ Created lead: {lead.name} (assigned to {agent.username})")
                
                print(f"✅ Created {len(sample_leads)} sample leads")
            else:
                print("ℹ️  Leads already exist, skipping sample lead creation")
            
            print("\n🎉 TeleCRM setup completed successfully!")
            print("\n📋 Login Credentials:")
            print("Admin Panel: http://localhost:8000/admin/")
            print("  └─ Username: admin")
            print("  └─ Password: admin123")
            print("\nCRM Dashboard: http://localhost:8000/")
            print("  └─ Username: admin")
            print("  └─ Password: admin123")
            print("\nAPI Endpoints: http://localhost:8000/api/")
            print("  └─ Agent Login: agent1 / password123")
            print("  └─ Agent Login: agent2 / password123")
            print("  └─ Agent Login: agent3 / password123")
            
            print("\n📱 Mobile App API Test:")
            print("POST /api/auth/login/ with:")
            print('{"username": "agent1", "password": "password123"}')
            
    except Exception as e:
        print(f"❌ Error during setup: {str(e)}")
        sys.exit(1)

def main():
    """Main setup function"""
    create_sample_data()

if __name__ == '__main__':
    main()