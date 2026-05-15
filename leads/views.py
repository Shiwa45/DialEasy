# leads/views.py - Complete Updated Version

import pandas as pd
import numpy as np
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from .models import Lead, CallLog, FollowUp, LeadUpload
from agents.models import AgentProfile
import csv
import io
import re
from datetime import datetime, timedelta
from django.views.decorators.http import require_POST
from leads.integration_models import IntegrationConfig
from leads.whatsapp_service import send_whatsapp_text
from .models import LeadNote

@login_required
def dashboard(request):
    """Dashboard view with key metrics and recent activities"""
    
    today = timezone.now().date()

    # Key metrics
    total_leads     = Lead.objects.count()
    converted_leads = Lead.objects.filter(status='converted').count()
    conversion_rate = round(converted_leads / total_leads * 100, 1) if total_leads else 0

    today_calls = CallLog.objects.filter(call_date__date=today).count()
    today_follow_ups = FollowUp.objects.filter(follow_up_date=today, is_completed=False).count()

    recent_leads = Lead.objects.select_related('assigned_agent').order_by('-created_at')[:10]

    # Pre-compute display fields for recent calls
    raw_calls = CallLog.objects.select_related('lead', 'agent').order_by('-call_date')[:10]
    recent_calls = []
    for c in raw_calls:
        secs = int(c.duration.total_seconds()) if c.duration else 0
        if secs:
            m, s = divmod(secs, 60)
            dur_display = f"{m}m {s}s" if m else f"{s}s"
        else:
            dur_display = '—'
        recent_calls.append({
            'lead':        c.lead,
            'agent':       c.agent,
            'disposition': c.disposition.replace('_', ' ').title() if c.disposition else '—',
            'duration':    dur_display,
            'call_date':   c.call_date,
        })

    status_distribution = Lead.objects.values('status').annotate(count=Count('id'))

    _tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
    top_agents = User.objects.filter(
        id__in=_tenant_agent_ids,
        call_logs__call_date__date=today,
    ).annotate(
        call_count=Count('call_logs', filter=Q(call_logs__call_date__date=today))
    ).order_by('-call_count')[:5]

    overdue_follow_ups = FollowUp.objects.filter(
        follow_up_date__lt=today, is_completed=False
    ).count()

    context = {
        'today':             today,
        'total_leads':       total_leads,
        'converted_leads':   converted_leads,
        'conversion_rate':   conversion_rate,
        'today_calls':       today_calls,
        'today_follow_ups':  today_follow_ups,
        'recent_leads':      recent_leads,
        'recent_calls':      recent_calls,
        'status_distribution': status_distribution,
        'top_agents':        top_agents,
        'overdue_follow_ups': overdue_follow_ups,
    }

    return render(request, 'leads/dashboard.html', context)


@login_required
def lead_list(request):
    """Display all leads with filtering and search"""
    
    leads = Lead.objects.select_related('assigned_agent').all()
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(company__icontains=search_query)
        )
    
    # Status filter
    status_filter = request.GET.get('status')
    if status_filter:
        leads = leads.filter(status=status_filter)
    
    # Agent filter
    agent_filter = request.GET.get('agent')
    if agent_filter:
        leads = leads.filter(assigned_agent_id=agent_filter)
    
    # Pagination
    paginator = Paginator(leads, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get agents for filter dropdown — scoped to this tenant only
    _tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
    agents = User.objects.filter(id__in=_tenant_agent_ids, is_active=True)
    
    context = {
        'page_obj': page_obj,
        'agents': agents,
        'search_query': search_query,
        'status_filter': status_filter,
        'agent_filter': agent_filter,
        'status_choices': Lead.STATUS_CHOICES,
    }
    
    return render(request, 'leads/lead_list.html', context)


@login_required
def lead_detail(request, lead_id):
    """Display detailed view of a single lead"""
    
    lead = get_object_or_404(Lead, id=lead_id)
    call_logs = CallLog.objects.filter(lead=lead).order_by('-call_date')
    follow_ups = FollowUp.objects.filter(lead=lead).order_by('-follow_up_date')
    
    context = {
        'lead': lead,
        'call_logs': call_logs,
        'follow_ups': follow_ups,
    }
    
    return render(request, 'leads/lead_detail.html', context)


@login_required
def upload_leads(request):
    """Handle lead file uploads with enhanced error handling"""
    
    if request.method == 'POST':
        uploaded_file = request.FILES.get('lead_file')
        
        if not uploaded_file:
            messages.error(request, 'Please select a file to upload.')
            return redirect('leads:upload_leads')
        
        # Validate file format
        file_extension = uploaded_file.name.lower().split('.')[-1]
        if file_extension not in ['csv', 'xlsx', 'xls']:
            messages.error(request, 'Please upload a CSV or Excel file.')
            return redirect('leads:upload_leads')
        
        try:
            # Create upload record
            upload_record = LeadUpload.objects.create(
                file=uploaded_file,
                uploaded_by=request.user,
                status='processing'
            )
            
            # Process the file
            success_count, error_count, errors = process_lead_file_enhanced(uploaded_file)
            
            # Update upload record
            upload_record.processed_records = success_count
            upload_record.failed_records = error_count
            upload_record.total_records = success_count + error_count
            upload_record.status = 'completed' if error_count == 0 else 'failed'
            
            if errors:
                upload_record.error_log = '\n'.join(errors[:50])  # Limit error log size
            
            upload_record.save()
            
            if success_count > 0:
                messages.success(
                    request, 
                    f'Successfully uploaded {success_count} leads. {error_count} failed.'
                )
                if errors:
                    # Show first few errors as warning
                    error_preview = '; '.join(errors[:3])
                    if len(errors) > 3:
                        error_preview += f"... and {len(errors) - 3} more errors"
                    messages.warning(request, f'Errors: {error_preview}')
            else:
                messages.error(request, 'No leads were uploaded. Please check your file format.')
                if errors:
                    error_preview = '; '.join(errors[:5])
                    messages.error(request, f'Errors found: {error_preview}')
                
        except Exception as e:
            upload_record.status = 'failed'
            upload_record.error_log = str(e)
            upload_record.save()
            messages.error(request, f'Error processing file: {str(e)}')
            
        return redirect('leads:upload_leads')
    
    # GET request - show upload form
    recent_uploads = LeadUpload.objects.filter(
        uploaded_by=request.user
    ).order_by('-created_at')[:10]
    
    context = {
        'recent_uploads': recent_uploads,
    }
    
    return render(request, 'leads/upload_leads.html', context)


def process_lead_file_enhanced(uploaded_file):
    """Enhanced CSV/Excel file processing with better error handling"""
    
    errors = []
    success_count = 0
    error_count = 0
    
    try:
        # Reset file pointer to beginning
        uploaded_file.seek(0)
        
        # Read file based on extension
        file_extension = uploaded_file.name.lower().split('.')[-1]
        
        if file_extension == 'csv':
            # Try different encodings for CSV
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)
                    content = uploaded_file.read().decode(encoding)
                    df = pd.read_csv(io.StringIO(content))
                    print(f"Successfully read CSV with encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"Error with encoding {encoding}: {e}")
                    continue
            
            if df is None:
                errors.append("Could not read CSV file. Please check file encoding.")
                return 0, 1, errors
                
        else:  # Excel files
            try:
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            except Exception as e:
                errors.append(f"Could not read Excel file: {str(e)}")
                return 0, 1, errors
        
        # Clean column names - remove extra spaces and normalize case
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
        
        print(f"Columns found: {list(df.columns)}")
        print(f"DataFrame shape: {df.shape}")
        print(f"First few rows:\n{df.head()}")
        
        # Define column mappings (flexible column name matching)
        column_mappings = {
            'name': ['name', 'full_name', 'customer_name', 'lead_name', 'contact_name'],
            'phone': ['phone', 'phone_number', 'mobile', 'contact_number', 'telephone', 'cell'],
            'email': ['email', 'email_address', 'mail', 'e_mail'],
            'company': ['company', 'company_name', 'organization', 'business', 'firm'],
            'source': ['source', 'lead_source', 'origin', 'channel']
        }
        
        # Map actual columns to required fields
        field_mappings = {}
        for required_field, possible_names in column_mappings.items():
            for possible_name in possible_names:
                if possible_name in df.columns:
                    field_mappings[required_field] = possible_name
                    break
        
        print(f"Field mappings: {field_mappings}")
        
        # Check for required columns
        if 'name' not in field_mappings:
            errors.append("Required column 'name' not found. Expected columns: name, phone")
            return 0, 1, errors
            
        if 'phone' not in field_mappings:
            errors.append("Required column 'phone' not found. Expected columns: name, phone")
            return 0, 1, errors
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Extract and clean data
                name = clean_text_field(row.get(field_mappings['name'], ''))
                phone = clean_phone_field(row.get(field_mappings['phone'], ''))
                
                # Validate required fields
                if not name:
                    errors.append(f"Row {index + 2}: Name is required and cannot be empty")
                    error_count += 1
                    continue
                
                if not phone:
                    errors.append(f"Row {index + 2}: Phone number is required and cannot be empty")
                    error_count += 1
                    continue
                
                # Validate phone number format
                if not is_valid_phone(phone):
                    errors.append(f"Row {index + 2}: Invalid phone number format: {phone}")
                    error_count += 1
                    continue
                
                # Check for duplicate phone number
                if Lead.objects.filter(phone=phone).exists():
                    errors.append(f"Row {index + 2}: Phone number {phone} already exists")
                    error_count += 1
                    continue
                
                # Prepare lead data
                lead_data = {
                    'name': name,
                    'phone': phone,
                }
                
                # Add optional fields if present and valid
                if 'email' in field_mappings:
                    email = clean_email_field(row.get(field_mappings['email'], ''))
                    if email and is_valid_email(email):
                        lead_data['email'] = email
                
                if 'company' in field_mappings:
                    company = clean_text_field(row.get(field_mappings['company'], ''))
                    if company:
                        lead_data['company'] = company
                
                if 'source' in field_mappings:
                    source = clean_text_field(row.get(field_mappings['source'], ''))
                    if source:
                        lead_data['source'] = source
                
                # Create lead
                Lead.objects.create(**lead_data)
                success_count += 1
                
            except Exception as e:
                errors.append(f"Row {index + 2}: {str(e)}")
                error_count += 1
                
    except Exception as e:
        errors.append(f"File processing error: {str(e)}")
        error_count = 1
    
    return success_count, error_count, errors


def clean_text_field(value):
    """Clean and validate text fields"""
    if pd.isna(value) or value is None:
        return ''
    
    text = str(value).strip()
    
    # Remove common invalid values
    invalid_values = ['', 'n/a', 'na', 'null', 'none', 'undefined', '-']
    if text.lower() in invalid_values:
        return ''
    
    return text


def clean_phone_field(value):
    """Clean and validate phone number field"""
    if pd.isna(value) or value is None:
        return ''
    
    # Convert to string and remove all non-digit characters except +
    phone = re.sub(r'[^\d+]', '', str(value))
    
    # Remove leading/trailing whitespace
    phone = phone.strip()
    
    # Handle common formatting issues
    if phone.startswith('0'):
        phone = phone[1:]  # Remove leading 0
    
    # Add country code if missing (assuming US/India)
    if len(phone) == 10 and phone.isdigit():
        phone = phone  # Default to US, change as needed
    
    return phone


def clean_email_field(value):
    """Clean and validate email field"""
    if pd.isna(value) or value is None:
        return ''
    
    email = str(value).strip().lower()
    
    # Remove common invalid values
    invalid_values = ['', 'n/a', 'na', 'null', 'none', 'undefined', '-']
    if email in invalid_values:
        return ''
    
    return email


def is_valid_phone(phone):
    """Validate phone number format"""
    if not phone:
        return False
    
    # Remove all non-digit characters for validation
    digits_only = re.sub(r'[^\d]', '', phone)
    
    # Check if it has reasonable length (7-15 digits)
    if len(digits_only) < 7 or len(digits_only) > 15:
        return False
    
    return True


def is_valid_email(email):
    """Basic email validation"""
    if not email:
        return False
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None


@login_required
def download_sample_csv(request):
    """Download a sample CSV file for lead upload"""
    
    # Create a sample CSV content
    csv_content = [
        ['name', 'phone', 'email', 'company', 'source'],
        ['John Doe', '+1234567890', 'john@example.com', 'ABC Company', 'Website'],
        ['Jane Smith', '+1987654321', 'jane@example.com', 'XYZ Corp', 'Referral'],
        ['Bob Johnson', '+1555123456', 'bob@example.com', 'Tech Solutions', 'Advertisement'],
        ['Alice Brown', '1-800-555-0199', 'alice@example.com', 'Marketing Inc', 'Social Media'],
        ['Charlie Wilson', '555.999.8888', 'charlie@example.com', 'Sales Pro', 'Cold Call']
    ]
    
    # Create HTTP response with CSV content
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sample_leads.csv"'
    
    writer = csv.writer(response)
    for row in csv_content:
        writer.writerow(row)
    
    return response


@login_required
def debug_csv_upload(request):
    """Debug view to analyze CSV files before upload"""
    
    if request.method == 'POST':
        uploaded_file = request.FILES.get('debug_file')
        
        if not uploaded_file:
            return JsonResponse({'error': 'No file uploaded'})
        
        try:
            # Reset file pointer
            uploaded_file.seek(0)
            
            # Try to read the file
            file_extension = uploaded_file.name.lower().split('.')[-1]
            
            debug_info = {
                'filename': uploaded_file.name,
                'size': uploaded_file.size,
                'extension': file_extension,
                'columns': [],
                'sample_data': [],
                'issues': [],
                'suggestions': []
            }
            
            if file_extension == 'csv':
                # Try different encodings
                encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
                df = None
                used_encoding = None
                
                for encoding in encodings:
                    try:
                        uploaded_file.seek(0)
                        content = uploaded_file.read().decode(encoding)
                        df = pd.read_csv(io.StringIO(content))
                        used_encoding = encoding
                        break
                    except:
                        continue
                
                if df is None:
                    debug_info['issues'].append('Could not read file with any encoding')
                    return JsonResponse(debug_info)
                
                debug_info['encoding_used'] = used_encoding
                
            else:
                try:
                    df = pd.read_excel(uploaded_file)
                except Exception as e:
                    debug_info['issues'].append(f'Excel read error: {str(e)}')
                    return JsonResponse(debug_info)
            
            # Analyze columns
            debug_info['original_columns'] = list(df.columns)
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
            debug_info['cleaned_columns'] = list(df.columns)
            debug_info['row_count'] = len(df)
            
            # Check for required columns
            required_columns = ['name', 'phone']
            column_mappings = {
                'name': ['name', 'full_name', 'customer_name', 'lead_name', 'contact_name'],
                'phone': ['phone', 'phone_number', 'mobile', 'contact_number', 'telephone', 'cell'],
                'email': ['email', 'email_address', 'mail', 'e_mail'],
                'company': ['company', 'company_name', 'organization', 'business', 'firm'],
                'source': ['source', 'lead_source', 'origin', 'channel']
            }
            
            found_mappings = {}
            for required_field, possible_names in column_mappings.items():
                for possible_name in possible_names:
                    if possible_name in df.columns:
                        found_mappings[required_field] = possible_name
                        break
            
            debug_info['found_mappings'] = found_mappings
            
            # Check for missing required columns
            missing_required = []
            for req_col in required_columns:
                if req_col not in found_mappings:
                    missing_required.append(req_col)
            
            if missing_required:
                debug_info['issues'].append(f"Missing required columns: {', '.join(missing_required)}")
                debug_info['suggestions'].append("Make sure your CSV has 'name' and 'phone' columns")
            
            # Analyze sample data
            sample_size = min(5, len(df))
            for i in range(sample_size):
                row_data = {}
                for field, col_name in found_mappings.items():
                    value = df.iloc[i][col_name]
                    if pd.isna(value):
                        row_data[field] = 'EMPTY'
                    else:
                        row_data[field] = str(value)[:50]  # Truncate long values
                debug_info['sample_data'].append(row_data)
            
            # Check for data quality issues
            if 'name' in found_mappings:
                empty_names = df[found_mappings['name']].isna().sum()
                if empty_names > 0:
                    debug_info['issues'].append(f"{empty_names} rows have empty names")
            
            if 'phone' in found_mappings:
                empty_phones = df[found_mappings['phone']].isna().sum()
                if empty_phones > 0:
                    debug_info['issues'].append(f"{empty_phones} rows have empty phone numbers")
                
                # Check phone number formats
                phone_col = df[found_mappings['phone']].dropna()
                invalid_phones = 0
                for phone in phone_col:
                    phone_str = re.sub(r'[^\d+]', '', str(phone))
                    if len(phone_str) < 7 or len(phone_str) > 15:
                        invalid_phones += 1
                
                if invalid_phones > 0:
                    debug_info['issues'].append(f"{invalid_phones} rows have invalid phone number formats")
            
            # Check for duplicates within the file
            if 'phone' in found_mappings:
                phone_col = df[found_mappings['phone']].dropna()
                duplicates = phone_col.duplicated().sum()
                if duplicates > 0:
                    debug_info['issues'].append(f"{duplicates} duplicate phone numbers found in file")
            
            # Add suggestions based on issues found
            if not debug_info['issues']:
                debug_info['suggestions'].append("File looks good! Ready for upload.")
            else:
                debug_info['suggestions'].extend([
                    "Fix the issues mentioned above before uploading",
                    "You can download the sample CSV to see the correct format",
                    "Make sure phone numbers are properly formatted",
                    "Remove duplicate entries"
                ])
            
            return JsonResponse(debug_info)
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error analyzing file: {str(e)}',
                'suggestions': ['Please check if the file is corrupted or in the wrong format']
            })
    
    return JsonResponse({'error': 'Invalid request method'})


@login_required 
def check_file_preview(request):
    """AJAX endpoint to preview CSV file before upload"""
    
    if request.method == 'POST' and request.FILES.get('preview_file'):
        uploaded_file = request.FILES['preview_file']
        
        try:
            # Reset file pointer
            uploaded_file.seek(0)
            
            # Read first few lines
            file_extension = uploaded_file.name.lower().split('.')[-1]
            
            if file_extension == 'csv':
                # Try UTF-8 first
                try:
                    content = uploaded_file.read().decode('utf-8')
                    lines = content.split('\n')[:6]  # First 6 lines
                except UnicodeDecodeError:
                    uploaded_file.seek(0)
                    content = uploaded_file.read().decode('latin-1')
                    lines = content.split('\n')[:6]
            else:
                # For Excel files, read with pandas
                df = pd.read_excel(uploaded_file, nrows=5)
                lines = [','.join(df.columns.astype(str))]
                for _, row in df.iterrows():
                    lines.append(','.join(row.astype(str)))
            
            return JsonResponse({
                'success': True,
                'preview_lines': lines,
                'total_lines': len(lines)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'No file provided'})


@login_required
def assign_leads(request):
    """Assign leads to agents"""
    
    unassigned_leads = Lead.objects.filter(assigned_agent__isnull=True)
    _tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
    agents = User.objects.filter(id__in=_tenant_agent_ids, is_active=True)
    
    context = {
        'unassigned_leads': unassigned_leads,
        'agents': agents,
    }
    
    return render(request, 'leads/assign_leads.html', context)


@login_required
def bulk_assign_leads(request):
    """Handle bulk assignment of leads to agents"""
    
    if request.method == 'POST':
        if request.POST.get('auto_assign'):
            _tenant_agent_ids = AgentProfile.objects.values_list('user_id', flat=True)
            agents = list(User.objects.filter(id__in=_tenant_agent_ids, is_active=True))
            if not agents:
                messages.error(request, 'No active agents available for assignment.')
                return redirect('leads:assign_leads')
                
            unassigned_leads = list(Lead.objects.filter(assigned_agent__isnull=True))
            if not unassigned_leads:
                messages.info(request, 'No unassigned leads available.')
                return redirect('leads:assign_leads')
                
            agent_count = len(agents)
            updates = []
            for i, lead in enumerate(unassigned_leads):
                lead.assigned_agent = agents[i % agent_count]
                updates.append(lead)
                
            Lead.objects.bulk_update(updates, ['assigned_agent'])
            messages.success(request, f'Successfully auto-assigned {len(updates)} leads among {agent_count} agent(s).')
            return redirect('leads:assign_leads')

        # Normal bulk assign
        lead_ids = request.POST.getlist('lead_ids')
        agent_id = request.POST.get('agent_id')
        
        if not lead_ids:
            messages.error(request, 'Please select at least one lead.')
            return redirect('leads:assign_leads')
        
        if not agent_id:
            messages.error(request, 'Please select an agent.')
            return redirect('leads:assign_leads')
        
        try:
            agent = User.objects.get(id=agent_id)
            updated_count = Lead.objects.filter(
                id__in=lead_ids
            ).update(assigned_agent=agent)
            
            messages.success(
                request, 
                f'Successfully assigned {updated_count} leads to {agent.username}.'
            )
            
        except User.DoesNotExist:
            messages.error(request, 'Selected agent does not exist.')
    return redirect('leads:assign_leads')


@login_required
def integrations_view(request):
    """View to configure & display webhook URLs for various lead sources."""
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to view integrations.')
        return redirect('leads:dashboard')

    from leads.integration_models import IntegrationConfig, IntegrationLog

    PLATFORMS = ['meta', 'indiamart', 'justdial', 'whatsapp']

    if request.method == 'POST':
        platform = request.POST.get('platform')
        if platform not in PLATFORMS:
            messages.error(request, 'Invalid platform.')
            return redirect('leads:integrations')

        config, _ = IntegrationConfig.objects.get_or_create(platform=platform)
        config.is_active = request.POST.get('is_active') == 'on'
        config.updated_by = request.user

        if platform == 'meta':
            config.app_id = request.POST.get('app_id', '').strip()
            config.app_secret = request.POST.get('app_secret', '').strip()
            config.page_access_token = request.POST.get('page_access_token', '').strip()
            config.verify_token = request.POST.get('verify_token', '').strip()

        elif platform == 'whatsapp':
            config.whatsapp_phone_number_id = request.POST.get('whatsapp_phone_number_id', '').strip()
            config.whatsapp_access_token = request.POST.get('whatsapp_access_token', '').strip()
            config.whatsapp_verify_token = request.POST.get('whatsapp_verify_token', '').strip()

        # IndiaMart and JustDial need no credentials – just activation
        config.save()
        messages.success(request, f'{config.get_platform_display()} integration saved successfully.')
        return redirect('leads:integrations')

    # ── Build context ────────────────────────────────────────────
    configs = {p: None for p in PLATFORMS}
    for cfg in IntegrationConfig.objects.all():
        configs[cfg.platform] = cfg

    domain = request.build_absolute_uri('/').rstrip('/')
    webhook_urls = {
        'meta':      f"{domain}/api/webhooks/meta/",
        'indiamart': f"{domain}/api/webhooks/indiamart/",
        'justdial':  f"{domain}/api/webhooks/justdial/",
        'whatsapp':  f"{domain}/api/webhooks/whatsapp/",
    }

    recent_logs = IntegrationLog.objects.order_by('-created_at')[:50]

    context = {
        'configs': configs,
        'webhook_urls': webhook_urls,
        'recent_logs': recent_logs,
    }
    return render(request, 'leads/integrations.html', context)


@login_required
@require_POST
def send_whatsapp_message(request, lead_id):
    """
    Send a WhatsApp message via the configured WhatsApp Cloud API.
    """
    lead = get_object_or_404(Lead, id=lead_id)
    message_body = request.POST.get('message', '').strip()
    
    if not message_body:
        messages.error(request, 'Message body cannot be empty.')
        return redirect(request.META.get('HTTP_REFERER', 'leads:dashboard'))
        
    if not lead.phone:
        messages.error(request, 'Lead does not have a phone number.')
        return redirect(request.META.get('HTTP_REFERER', 'leads:dashboard'))

    # Get WhatsApp Config
    config = IntegrationConfig.objects.filter(platform='whatsapp', is_active=True).first()
    if not config or not config.whatsapp_phone_number_id or not config.whatsapp_access_token:
        messages.error(request, 'WhatsApp integration is not configured or inactive.')
        return redirect(request.META.get('HTTP_REFERER', 'leads:dashboard'))
        
    try:
        # Send message
        resp = send_whatsapp_text(
            phone_number_id=config.whatsapp_phone_number_id,
            access_token=config.whatsapp_access_token,
            to=lead.phone,
            body=message_body
        )
        
        # Log as a LeadNote
        LeadNote.objects.create(
            lead=lead,
            author=request.user,
            note_type='whatsapp',
            content=f"Sent WhatsApp Message:\n{message_body}"
        )
        
        messages.success(request, 'WhatsApp message sent successfully.')
    except Exception as e:
        messages.error(request, f'Failed to send WhatsApp message: {str(e)}')


@login_required
def settings_dispositions(request):
    """Manage call dispositions. Staff-only; dispositions are shared across all tenants."""
    if not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('leads:dashboard')

    from tenants.models import Disposition

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            label = request.POST.get('label', '').strip()
            value = request.POST.get('value', '').strip()
            color = request.POST.get('color', 'default')
            triggers_follow_up = request.POST.get('triggers_follow_up') == 'on'
            updates_lead_status = request.POST.get('updates_lead_status', '').strip()
            sort_order = int(request.POST.get('sort_order', 0) or 0)
            if label and value:
                if Disposition.objects.filter(value=value).exists():
                    messages.error(request, f'A disposition with value "{value}" already exists.')
                else:
                    Disposition.objects.create(
                        label=label,
                        value=value,
                        color=color,
                        triggers_follow_up=triggers_follow_up,
                        updates_lead_status=updates_lead_status,
                        sort_order=sort_order,
                        is_active=True,
                    )
                    messages.success(request, f'Disposition "{label}" created.')
            else:
                messages.error(request, 'Label and value are required.')

        elif action == 'edit':
            disp_id = request.POST.get('disp_id')
            d = get_object_or_404(Disposition, pk=disp_id)
            d.label = request.POST.get('label', d.label).strip()
            d.color = request.POST.get('color', d.color)
            d.triggers_follow_up = request.POST.get('triggers_follow_up') == 'on'
            d.updates_lead_status = request.POST.get('updates_lead_status', '').strip()
            d.sort_order = int(request.POST.get('sort_order', d.sort_order) or d.sort_order)
            d.is_active = request.POST.get('is_active') == 'on'
            d.save()
            messages.success(request, f'Disposition "{d.label}" updated.')

        elif action == 'delete':
            disp_id = request.POST.get('disp_id')
            d = get_object_or_404(Disposition, pk=disp_id)
            label = d.label
            d.delete()
            messages.success(request, f'Disposition "{label}" deleted.')

        return redirect('leads:settings_dispositions')

    dispositions = Disposition.objects.all().order_by('sort_order', 'label')
    lead_statuses = [s[0] for s in Lead.STATUS_CHOICES]
    color_choices = Disposition.COLOR_CHOICES

    return render(request, 'leads/settings_dispositions.html', {
        'dispositions': dispositions,
        'lead_statuses': lead_statuses,
        'color_choices': color_choices,
    })

    return redirect(request.META.get('HTTP_REFERER', 'leads:dashboard'))