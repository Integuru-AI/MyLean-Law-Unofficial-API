from curl_cffi import requests
from datetime import datetime, timedelta


def run(headers, user_input):
    """Fetch calendar time entries for a given date."""
    # Validate input
    date_str = user_input.get("date")
    if not date_str:
        return {"status_code": 400, "body": {"error": "date is required"}}

    # Validate date format
    try:
        start_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return {"status_code": 400, "body": {"error": "date must be in YYYY-MM-DD format"}}

    # endDate is always startDate + 1 day
    end_date = start_date + timedelta(days=1)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    try:
        # Fetch user profile to derive account_id and company_id
        me_data = _fetch_me(headers)
        if me_data is None:
            return {"status_code": 401, "body": {"error": "Session expired"}}

        # Prefer stored header if present; otherwise fall back to me["id"]
        account_id = headers.get("x-leanlaw-accountid") or me_data.get("id", "")
        company_id = me_data.get("company", {}).get("id", "")

        # Fetch entries for the given date
        result = _fetch_entries(headers, account_id, company_id, start_date_str, end_date_str)
        return result
    except Exception as e:
        return {"status_code": 500, "body": {"error": str(e)}}


# === PRIVATE ===


def _fetch_me(headers):
    """Fetch the user profile from /v1/me (works without x-leanlaw-accountid)."""
    base_url = BASE_URL

    req_headers = {
        "Cookie": headers.get("Cookie", ""),
        "x-leanlaw-source": headers.get("x-leanlaw-source", "myleanlaw"),
        "x-leanlaw-version": headers.get("x-leanlaw-version", "v1"),
        "accept": "application/json, text/plain, */*",
        "origin": "https://next.myleanlaw.co",
        "referer": "https://next.myleanlaw.co/",
    }
    # Include x-leanlaw-accountid only if available
    if headers.get("x-leanlaw-accountid"):
        req_headers["x-leanlaw-accountid"] = headers["x-leanlaw-accountid"]

    me_response = requests.get(
        f"{base_url}/v1/me?timeOffset=300",
        headers=req_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if me_response.status_code in (401, 403, 302):
        return None
    if "login" in me_response.url.lower():
        return None

    if me_response.status_code != 200:
        raise Exception("Failed to fetch user info")

    return me_response.json()


def _fetch_entries(headers, account_id, company_id, start_date_str, end_date_str):
    """Fetch time entries for the given date range."""
    base_url = BASE_URL

    params = {
        "account": account_id,
        "billed": "any",
        "startDate": start_date_str,
        "endDate": end_date_str,
        "timeOffset": "300",
    }

    entry_headers = {
        "Cookie": headers.get("Cookie", ""),
        "x-leanlaw-accountid": account_id,
        "x-leanlaw-source": headers.get("x-leanlaw-source", "myleanlaw"),
        "x-leanlaw-version": headers.get("x-leanlaw-version", "v1"),
        "x-leanlaw-companyid": company_id,
        "accept": "application/json, text/plain, */*",
        "origin": "https://next.myleanlaw.co",
        "referer": "https://next.myleanlaw.co/",
    }

    response = requests.get(
        f"{base_url}/v1/entries",
        params=params,
        headers=entry_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if response.status_code == 401 or response.status_code == 403:
        return {"status_code": 401, "body": {"error": "Session expired"}}

    # Check for login page redirect (session expired)
    if "login" in response.url.lower() or response.status_code == 302:
        return {"status_code": 401, "body": {"error": "Session expired"}}

    if response.status_code != 200:
        return {"status_code": response.status_code, "body": {"error": "Failed to fetch entries"}}

    data = response.json()

    return {"status_code": 200, "body": data}
