from curl_cffi import requests as cffi_requests


def run(headers, user_input):
    """List matters associated with a specific client. Returns matter IDs needed for create_expense."""
    base_url = BASE_URL

    session = cffi_requests.Session(impersonate="chrome131")

    # Validate required input
    client_id = user_input.get("client_id")
    if not client_id:
        return {'status_code': 400, 'body': {'error': 'client_id is required'}}

    search = user_input.get("search", "")

    # Step 1: Fetch current user info to get accountId and companyId for headers
    me_result = _fetch_me(session, base_url, headers)
    if me_result.get("error"):
        return me_result["error"]

    account_id = me_result["account_id"]
    company_id = me_result["company_id"]

    # Build API headers
    api_headers = {
        **headers,
        "accept": "application/json, text/plain, */*",
        "x-leanlaw-accountid": account_id,
        "x-leanlaw-companyid": company_id,
        "x-leanlaw-source": "myleanlaw",
        "x-leanlaw-version": "v1",
        "origin": APP_URL,
        "referer": f"{APP_URL}/",
    }

    # Step 2: Get matters for the specified client
    matters_result = _fetch_matters(session, base_url, api_headers, client_id, search)
    if matters_result.get("error"):
        return matters_result["error"]

    matters = matters_result["data"]

    # Return matter list with IDs
    result = []
    for matter in matters:
        result.append({
            "id": matter.get("id"),
            "name": matter.get("name"),
            "label": matter.get("label"),
            "reference": matter.get("reference"),
            "client_id": matter.get("clientId"),
            "client_number": matter.get("clientNumber"),
            "billing_type": matter.get("billingType"),
        })

    return {'status_code': 200, 'body': {'matters': result, 'count': len(result)}}


# === PRIVATE ===

def _fetch_me(session, base_url, headers):
    """Fetch current user info to get accountId and companyId."""
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
    if me_resp.status_code == 401 or me_resp.status_code == 302:
        return {"error": {'status_code': 401, 'body': {'error': 'Session expired'}}}
    if me_resp.status_code != 200:
        return {"error": {'status_code': me_resp.status_code, 'body': {'error': f'Failed to fetch user info: {me_resp.status_code}'}}}

    me_data = me_resp.json()
    if 'id' not in me_data:
        return {"error": {'status_code': 401, 'body': {'error': 'Session expired'}}}

    account_id = me_data['id']
    company_id = me_data.get('company', {}).get('id', '')
    return {"account_id": account_id, "company_id": company_id}


def _fetch_matters(session, base_url, api_headers, client_id, search):
    """Fetch matters for a specific client."""
    params = (
        f"involved=false&originating=false&reviewer=false"
        f"&primary=false&archived=false&search={search}"
        f"&clientId={client_id}"
    )
    resp = session.get(
        f"{base_url}/v1/matters/options?{params}",
        headers=api_headers,
        timeout=30
    )

    if resp.status_code == 401:
        return {"error": {'status_code': 401, 'body': {'error': 'Session expired'}}}
    if resp.status_code != 200:
        return {"error": {'status_code': resp.status_code, 'body': {'error': f'Failed to fetch matters: {resp.text}'}}}

    return {"data": resp.json()}
