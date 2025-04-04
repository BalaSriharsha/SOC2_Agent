from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Headless=False to allow manual login
    page = browser.new_page()
    page.goto("https://console.aws.amazon.com/")
    input("Please log in to the AWS Console and press Enter to continue...")
    storage = page.context.storage_state()
    with open("aws_session.json", "w") as f:
        json.dump(storage, f)
    print("Session state saved to aws_session.json")
    browser.close()
