"""Helper script to find your Instagram Business Account ID.

This script helps you find the correct Instagram Business Account ID
that should be used for INSTAGRAM_ACCOUNT_ID.

Usage:
    python scripts/find_instagram_account_id.py
"""

import sys
import requests
from pathlib import Path
import os

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import INSTAGRAM_ACCESS_TOKEN


def main():
    """Find Instagram Business Account ID."""
    
    access_token = INSTAGRAM_ACCESS_TOKEN or os.getenv("INSTAGRAM_ACCESS_TOKEN")
    
    if not access_token:
        print("Error: INSTAGRAM_ACCESS_TOKEN not set", file=sys.stderr)
        print("Please set INSTAGRAM_ACCESS_TOKEN environment variable or in .env file", file=sys.stderr)
        sys.exit(1)
    
    print("Finding your Instagram Business Account ID...")
    print("=" * 60)
    
    try:
        # Step 1: Get your Facebook User ID and Pages
        print("\n1. Getting your Facebook Pages...")
        url = "https://graph.facebook.com/v18.0/me/accounts"
        params = {
            "access_token": access_token,
            "fields": "id,name,instagram_business_account",
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        pages_data = response.json()
        
        if "data" not in pages_data or not pages_data["data"]:
            print("\n❌ No Facebook Pages found!")
            print("\nYou need to:")
            print("1. Create a Facebook Page")
            print("2. Connect it to an Instagram Business Account")
            print("3. Grant your app permissions to access the page")
            sys.exit(1)
        
        print(f"\n✓ Found {len(pages_data['data'])} Facebook Page(s):\n")
        
        instagram_accounts = []
        
        for page in pages_data["data"]:
            page_id = page.get("id")
            page_name = page.get("name", "Unknown")
            instagram_account = page.get("instagram_business_account")
            
            print(f"  Page: {page_name}")
            print(f"  Page ID: {page_id}")
            
            if instagram_account:
                ig_account_id = instagram_account.get("id")
                print(f"  ✓ Instagram Business Account ID: {ig_account_id}")
                instagram_accounts.append({
                    "page_name": page_name,
                    "page_id": page_id,
                    "instagram_account_id": ig_account_id,
                })
            else:
                print(f"  ⚠ No Instagram Business Account connected")
            
            print()
        
        if not instagram_accounts:
            print("\n❌ No Instagram Business Accounts found!")
            print("\nYou need to:")
            print("1. Convert your Instagram account to a Business Account")
            print("2. Connect it to your Facebook Page")
            print("3. Make sure your access token has 'instagram_basic' and 'pages_read_engagement' permissions")
            sys.exit(1)
        
        # Step 2: Verify the Instagram Account ID
        print("\n2. Verifying Instagram Business Account ID(s)...\n")
        
        for account in instagram_accounts:
            ig_id = account["instagram_account_id"]
            print(f"  Testing ID: {ig_id} (from page: {account['page_name']})")
            
            # Try to get account info
            verify_url = f"https://graph.facebook.com/v18.0/{ig_id}"
            verify_params = {
                "access_token": access_token,
                "fields": "id,username,name",
            }
            
            verify_response = requests.get(verify_url, params=verify_params)
            
            if verify_response.status_code == 200:
                account_info = verify_response.json()
                username = account_info.get("username", "Unknown")
                name = account_info.get("name", "Unknown")
                print(f"  ✓ Valid! Username: @{username}, Name: {name}")
                print(f"\n  ✅ Use this ID in your .env file:")
                print(f"     INSTAGRAM_ACCOUNT_ID={ig_id}\n")
            else:
                error_data = verify_response.json()
                print(f"  ❌ Error: {error_data.get('error', {}).get('message', 'Unknown error')}")
                print()
        
        # Summary
        if len(instagram_accounts) == 1:
            print("\n" + "=" * 60)
            print("✅ Found your Instagram Business Account ID!")
            print(f"   INSTAGRAM_ACCOUNT_ID={instagram_accounts[0]['instagram_account_id']}")
            print("\nAdd this to your .env file.")
        else:
            print("\n" + "=" * 60)
            print("✅ Found multiple Instagram Business Accounts!")
            print("Choose the one you want to use and add it to your .env file.")
        
    except requests.RequestException as e:
        print(f"\n❌ API Error: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Details: {error_data}", file=sys.stderr)
            except:
                print(f"   Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
