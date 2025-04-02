import datetime
from evidence_collector import PlaywrightCollector, Boto3Collector

class SOC2Agent:
    def __init__(self):
        self.playwright_collector = PlaywrightCollector()
        self.boto3_collector = Boto3Collector()

    def process_prompt(self, prompt: str):
        lower_prompt = prompt.lower()
        print(f"Processing prompt: {prompt}")

        if "iam role changes" in lower_prompt:
            print("Detected IAM role changes evidence request.")
            self.handle_iam_role_changes(prompt)
        elif "access review" in lower_prompt and "iam" in lower_prompt:
            print("Detected IAM access review evidence request.")
            self.handle_iam_access_review(prompt)
        elif "cloudtrail" in lower_prompt:
            print("Detected CloudTrail logs evidence request.")
            self.handle_cloudtrail_logs(prompt)
        elif "vpc flow logs" in lower_prompt:
            print("Detected VPC Flow Logs evidence request.")
            self.handle_vpc_flow_logs(prompt)
        else:
            print("Prompt did not match any known evidence type.")
            print("Please try again with a valid SOC2 prompt.")

    def handle_iam_role_changes(self, prompt: str):
        days = 30  # Default to last 30 days
        start_time = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        end_time = datetime.datetime.utcnow()
        evidence_dir = f"evidence/{datetime.datetime.utcnow().strftime('%Y-%m-%d')}/iam_role_changes"
        self.boto3_collector.collect_iam_role_changes(start_time, end_time, evidence_dir)

    def handle_iam_access_review(self, prompt: str):
        evidence_dir = f"evidence/{datetime.datetime.utcnow().strftime('%Y-%m-%d')}/access_review"
        # Capture screenshot of IAM users page
        self.playwright_collector.capture_iam_users_page(evidence_dir)
        # Generate IAM credential report
        self.boto3_collector.collect_iam_access_review(evidence_dir)

    def handle_cloudtrail_logs(self, prompt: str):
        days = 7  # Default to last 7 days
        start_time = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        end_time = datetime.datetime.utcnow()
        evidence_dir = f"evidence/{datetime.datetime.utcnow().strftime('%Y-%m-%d')}/cloudtrail_logs"
        self.boto3_collector.collect_cloudtrail_logs(start_time, end_time, evidence_dir)

    def handle_vpc_flow_logs(self, prompt: str):
        # For demonstration, using a placeholder VPC ID.
        # Replace with your actual VPC ID or extract from the prompt.
        vpc_id = "vpc-xxxxxxxx"  
        evidence_dir = f"evidence/{datetime.datetime.utcnow().strftime('%Y-%m-%d')}/vpc_flow_logs"
        self.boto3_collector.collect_vpc_flow_logs(vpc_id, evidence_dir)
