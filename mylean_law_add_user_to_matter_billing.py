from curl_cffi import requests


def run(headers, user_input):
    """Add a user to a matter's Billing and Rates section."""
    base_url = BASE_URL

    # Validate input
    client_id = user_input.get("client_id")
    if not client_id:
        return {"status_code": 400, "body": {"error": "client_id is required"}}

    user_id = user_input.get("user_id")
    if not user_id:
        return {"status_code": 400, "body": {"error": "user_id is required"}}

    matter_name = user_input.get("matter_name", "General").strip()

    try:
        result = _add_user_to_matter(headers, base_url, client_id, user_id, matter_name)
        return result
    except Exception as e:
        return {"status_code": 500, "body": {"error": str(e)}}


# === PRIVATE ===


def _add_user_to_matter(headers, base_url, client_id, user_id, matter_name):
    """Add user to matter billing via API calls."""
    # Step 1: Resolve account/company IDs from /v1/me
    api_headers = {
        "Cookie": headers.get("Cookie", ""),
        "accept": "application/json, text/plain, */*",
        "x-leanlaw-source": headers.get("x-leanlaw-source", "myleanlaw"),
        "x-leanlaw-version": headers.get("x-leanlaw-version", "v1"),
        "origin": "https://next.myleanlaw.co",
        "referer": "https://next.myleanlaw.co/",
    }

    me_resp = requests.get(
        f"{base_url}/v1/me",
        headers=api_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if me_resp.status_code in (401, 403) or me_resp.status_code == 302:
        return {"status_code": 401, "body": {"error": "Session expired"}}

    if me_resp.status_code != 200:
        return {"status_code": me_resp.status_code, "body": {"error": "Failed to resolve account info"}}

    me_data = me_resp.json()
    account_id = headers.get("x-leanlaw-accountid") or me_data.get("id")
    company_id = headers.get("x-leanlaw-companyid") or me_data.get("company", {}).get("id")

    # Build full API headers
    api_headers["x-leanlaw-accountid"] = account_id
    api_headers["x-leanlaw-companyid"] = company_id

    # Step 1b: Resolve matter_id from client_id
    client_resp = requests.get(
        f"{base_url}/v1/clients/{client_id}?matters=include&scope=all&timeOffset=360",
        headers=api_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if client_resp.status_code in (401, 403) or client_resp.status_code == 302:
        return {"status_code": 401, "body": {"error": "Session expired"}}

    if client_resp.status_code != 200:
        error_detail = client_resp.text
        try:
            error_detail = client_resp.json()
        except Exception:
            pass
        return {
            "status_code": client_resp.status_code,
            "body": {
                "error": "Failed to fetch client",
                "client_id": client_id,
                "api_status": client_resp.status_code,
                "detail": error_detail,
            },
        }

    client_data = client_resp.json()
    matters = client_data.get("matters", [])

    if not matters:
        return {"status_code": 404, "body": {"error": "No matters found for this client", "client_id": client_id}}

    # Find the matter - by name if provided, otherwise use first matter
    if matter_name:
        matched = [m for m in matters if m.get("name", "").lower() == matter_name.lower()]
        if not matched:
            available = [m.get("name", "") for m in matters]
            return {
                "status_code": 404,
                "body": {
                    "error": f"Matter '{matter_name}' not found for this client",
                    "available_matters": available,
                },
            }
        matter_id = matched[0]["id"]
    else:
        # Default to the first matter
        matter_id = matters[0]["id"]

    # Step 2: Get the current matter to retrieve existing users
    matter_resp = requests.get(
        f"{base_url}/v1/matters/{matter_id}?timeOffset=360",
        headers=api_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if matter_resp.status_code in (401, 403) or matter_resp.status_code == 302:
        return {"status_code": 401, "body": {"error": "Session expired"}}

    if matter_resp.status_code != 200:
        error_detail = matter_resp.text
        try:
            error_detail = matter_resp.json()
        except Exception:
            pass
        return {
            "status_code": matter_resp.status_code,
            "body": {
                "error": "Failed to fetch matter",
                "matter_id": matter_id,
                "api_status": matter_resp.status_code,
                "detail": error_detail,
            },
        }

    matter_data = matter_resp.json()
    existing_users = matter_data.get("users", [])
    billing = matter_data.get("billing", {"type": "hours"})
    restricted = matter_data.get("restricted", False)

    # Check if user is already on the matter
    existing_ids = [u["id"] for u in existing_users]
    if user_id in existing_ids:
        return {"status_code": 409, "body": {"error": "User is already assigned to this matter"}}

    # Step 3: Get the user's account to retrieve their rate info
    account_resp = requests.get(
        f"{base_url}/v1/accounts/{user_id}",
        headers=api_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if account_resp.status_code in (401, 403) or account_resp.status_code == 302:
        return {"status_code": 401, "body": {"error": "Session expired"}}

    if account_resp.status_code != 200:
        return {"status_code": account_resp.status_code, "body": {"error": "Failed to fetch user account"}}

    account_data = account_resp.json()

    # Build rate info from account
    standard_rate = account_data.get("rates", {}).get("standard", 0)
    rate_label = "Standard"
    rate_id = f"{user_id}_rate_0_Standard_{int(standard_rate)}"

    # Build rate list
    rate_list = [{"label": rate_label, "amount": standard_rate, "_id": rate_id}]

    # Step 4: Build the new user entry (matching captured format)
    new_user = {
        "account": {
            "features": account_data.get("features", {}),
            "id": account_data.get("id", user_id),
            "href": f"/v1/accounts/{user_id}",
            "disabled": account_data.get("disabled", False),
            "exempt": account_data.get("exempt", False),
            "registered": account_data.get("registered", True),
            "registrant": account_data.get("registrant", False),
            "primary": account_data.get("primary", True),
            "email": account_data.get("email", ""),
            "name": account_data.get("name", ""),
            "first": account_data.get("first", ""),
            "last": account_data.get("last", ""),
            "initials": account_data.get("initials", ""),
            "rates": account_data.get("rates", {}),
            "access": account_data.get("access", {}),
            "role": account_data.get("role", ""),
            "revenue": account_data.get("revenue", {"type": "self"}),
            "$original": {
                "id": account_data.get("id", user_id),
                "href": f"/v1/accounts/{user_id}",
                "disabled": account_data.get("disabled", False),
                "exempt": account_data.get("exempt", False),
                "registered": account_data.get("registered", True),
                "registrant": account_data.get("registrant", False),
                "primary": account_data.get("primary", True),
                "email": account_data.get("email", ""),
                "name": account_data.get("name", ""),
                "first": account_data.get("first", ""),
                "last": account_data.get("last", ""),
                "initials": account_data.get("initials", ""),
                "rates": account_data.get("rates", {}),
                "access": account_data.get("access", {}),
                "role": account_data.get("role", ""),
                "revenue": account_data.get("revenue", {"type": "self"}),
            },
            "rateList": rate_list,
            "settings": account_data.get("settings", {}),
        },
        "id": user_id,
        "name": account_data.get("name", ""),
        "rate": {"label": rate_label, "amount": standard_rate, "_id": rate_id},
        "active": True,
    }

    # Step 5: Build the full users list for the PUT (existing users enriched + new user)
    # The frontend sends ALL users with full account data. For existing users from GET,
    # they only have minimal fields. We send them as-is with active: true added.
    users_payload = []
    for u in existing_users:
        user_entry = {
            "name": u.get("name", ""),
            "originating": u.get("originating", False),
            "primary": u.get("primary", False),
            "initials": u.get("initials", ""),
            "id": u["id"],
            "rate": u.get("rate", {}),
            "active": True,
        }
        users_payload.append(user_entry)

    # Add the new user
    users_payload.append(new_user)

    # Step 6: PUT the rates
    put_payload = {
        "users": users_payload,
        "billing": billing,
        "restricted": restricted,
        "rateOptions": {"updateEntries": False},
    }

    put_headers = {
        **api_headers,
        "content-type": "application/json;charset=UTF-8",
    }

    put_resp = requests.put(
        f"{base_url}/v1/matters/{matter_id}/rates?timeOffset=360",
        json=put_payload,
        headers=put_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if put_resp.status_code in (401, 403) or put_resp.status_code == 302:
        return {"status_code": 401, "body": {"error": "Session expired"}}

    if put_resp.status_code >= 400:
        error_body = put_resp.text
        try:
            error_body = put_resp.json()
        except Exception:
            pass
        return {"status_code": put_resp.status_code, "body": {"error": error_body}}

    result = {}
    try:
        result = put_resp.json()
    except Exception:
        result = {"raw": put_resp.text}

    return {
        "status_code": 200,
        "body": {
            "success": True,
            "user_added": account_data.get("name", user_id),
            "matter_id": matter_id,
            "total_users": len(users_payload),
            "response": result,
        },
    }
