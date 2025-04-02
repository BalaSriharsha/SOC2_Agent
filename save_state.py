from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://console.aws.amazon.com/")
    input("Please log in to the AWS Console and then press Enter here...")
    context.storage_state(path="aws_login_state.json")
    browser.close()
