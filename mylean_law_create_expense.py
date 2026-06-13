from curl_cffi import requests as cffi_requests


def run(headers, user_input):
    """Create a new expense entry on a matter in LeanLaw."""
    base_url = BASE_URL

    # Build a session for consistent TLS fingerprinting
    session = cffi_requests.Session(impersonate="chrome131")

    # Validate required inputs
    matter_id = user_input.get("matter_id")
    if not matter_id:
        return {'status_code': 400, 'body': {'error': 'matter_id is required'}}

    date = user_input.get("date")
    if not date:
        return {'status_code': 400, 'body': {'error': 'date is required (YYYY-MM-DD)'}}

    description = user_input.get("description")
    if not description:
        return {'status_code': 400, 'body': {'error': 'description is required'}}

    amount = user_input.get("amount")
    if amount is None:
        return {'status_code': 400, 'body': {'error': 'amount is required'}}

    # Ensure amount is a string (API expects string format)
    amount_str = str(amount)

    # Optional fields
    account_id = user_input.get("account_id")
    code_id = user_input.get("code")
    custom_flag = user_input.get("custom_flag", False)

    try:
        result = _create_expense(session, headers, base_url, matter_id, date, description, amount_str, account_id, code_id, custom_flag)
        return result
    except Exception as e:
        return {'status_code': 500, 'body': {'error': str(e)}}


# === PRIVATE ===


def _create_expense(session, headers, base_url, matter_id, date, description, amount_str, account_id, code_id, custom_flag):
    """Create an expense via the LeanLaw API."""

    # Step 1: Fetch current user info to get accountId and companyId for headers
    me_headers = {
        **headers,
        "accept": "application/json, text/plain, */*",
        "origin": APP_URL,
        "referer": f"{APP_URL}/",
    }
    me_resp = session.get(
        f"{base_url}/v1/me",
        headers=me_headers,
        timeout=30
    )
    if me_resp.status_code == 401 or (me_resp.status_code == 302):
        return {'status_code': 401, 'body': {'error': 'Session expired'}}
    if me_resp.status_code == 403:
        return {'status_code': 403, 'body': {'error': f'Access denied: {me_resp.status_code} - {me_resp.text[:200]}'}}
    if me_resp.status_code != 200:
        return {'status_code': me_resp.status_code, 'body': {'error': f'Failed to fetch user info: {me_resp.status_code}'}}

    me_data = me_resp.json()

    # Check if we got redirected to login
    if 'id' not in me_data:
        return {'status_code': 401, 'body': {'error': 'Session expired'}}

    account_id_header = me_data['id']
    company_id_header = me_data.get('company', {}).get('id', '')

    # Build API headers
    api_headers = {
        **headers,
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "x-leanlaw-accountid": account_id_header,
        "x-leanlaw-companyid": company_id_header,
        "x-leanlaw-source": "myleanlaw",
        "x-leanlaw-version": "v1",
        "origin": APP_URL,
        "referer": f"{APP_URL}/",
    }

    # Step 2: Fetch matter with client info to build the payload
    matter_resp = session.get(
        f"{base_url}/v1/matters/{matter_id}/matterwithclient",
        headers=api_headers,
        timeout=30
    )
    if matter_resp.status_code == 401:
        return {'status_code': 401, 'body': {'error': 'Session expired'}}
    if matter_resp.status_code != 200:
        return {'status_code': matter_resp.status_code, 'body': {'error': f'Failed to fetch matter: {matter_resp.text}'}}

    matter_data = matter_resp.json()
    client_data = matter_data.get('client', {})

    # Build account object for the payload
    account_obj = None
    if account_id:
        # Fetch accounts list to find the specified account
        accounts_resp = session.get(
            f"{base_url}/v1/accounts?timeOffset=420",
            headers=api_headers,
            timeout=30
        )
        if accounts_resp.status_code == 200:
            accounts_list = accounts_resp.json()
            if isinstance(accounts_list, list):
                for acct in accounts_list:
                    if acct.get('id') == account_id:
                        account_obj = acct
                        break
            if not account_obj:
                return {'status_code': 400, 'body': {'error': f'Account not found: {account_id}'}}
    else:
        # Default to current user's account info from /me
        account_obj = {
            "id": me_data['id'],
            "name": me_data.get('name', ''),
            "first": me_data.get('first', ''),
            "last": me_data.get('last', ''),
            "email": me_data.get('email', ''),
            "role": me_data.get('role', ''),
        }

    # Build code object
    code_obj = None
    if code_id:
        code_obj = {"id": code_id}

    # Build the expense payload (matching frontend structure)
    payload = {
        "client": client_data,
        "matter": matter_data,
        "description": description,
        "code": code_obj,
        "account": account_obj,
        "standard": None,
        "date": date,
        "accountingService": {},
        "amount": amount_str,
        "method": "Expense Page",
        "customFlag": custom_flag,
    }

    # Step 3: Create the expense
    resp = session.post(
        f"{base_url}/v1/matters/{matter_id}/expenses?timeOffset=420",
        json=payload,
        headers=api_headers,
        timeout=30
    )

    if resp.status_code == 401:
        return {'status_code': 401, 'body': {'error': 'Session expired'}}

    if resp.status_code in (200, 201):
        try:
            result = resp.json()
        except Exception:
            result = {"message": "Expense created successfully"}
        return {'status_code': 200, 'body': result}
    else:
        try:
            error_body = resp.json()
        except Exception:
            error_body = resp.text
        return {'status_code': resp.status_code, 'body': {'error': error_body}}
