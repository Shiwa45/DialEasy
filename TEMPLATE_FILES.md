# Template files referenced by Django views

This file lists the template paths referenced by view functions and decorators in the project.

## Templates used in `agents/views.py`

- `agents/agent_list.html`
- `agents/agent_detail.html`
- `agents/create_agent.html`
- `agents/agent_performance.html`
- `agents/update_agent.html`
- `agents/agent_dashboard.html`
- `agents/agent_leads.html`
- `agents/agent_activity_list.html`
- `agents/agent_activity_detail.html`

## Templates used in `leads/views.py`

- `leads/dashboard.html`
- `leads/lead_list.html`
- `leads/lead_detail.html`
- `leads/upload_leads.html`
- `leads/assign_leads.html`
- `leads/integrations.html`

## Templates used in `tenants/feature_gates.py`

- `tenants/feature_unavailable.html`

## Notes

- The list is derived from direct `render(request, ...)` calls and the feature-gating decorator in view-related Python files.
- There are dynamic `template_name` values in `leads/whatsapp_service.py` and `leads/whatsapp_service_v2.py`, but those are not explicit static template paths in view functions.
- No other `render(request, ...)` or `template_name` references were found in non-virtualenv Python sources outside the above files.
