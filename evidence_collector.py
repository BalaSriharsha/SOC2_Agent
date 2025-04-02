import os
import json
import time
import datetime
import boto3
from playwright.sync_api import sync_playwright

# Set default region from environment or use 'us-east-1'
DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

class PlaywrightCollector:
    def __init__(self):
        pass

    def capture_iam_users_page(self, evidence_dir: str):
        os.makedirs(evidence_dir, exist_ok=True)
        screenshot_path = os.path.join(evidence_dir, "IAM_users_list.png")
        print(f"Capturing IAM users page screenshot to {screenshot_path}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Use a persistent context with stored AWS login state.
            context = browser.new_context(storage_state="aws_login_state.json")
            page = context.new_page()
            page.goto("https://console.aws.amazon.com/iamv2/home?#/users")
            # Wait until the table loads (adjust selector as needed).
            page.wait_for_selector("table", timeout=15000)
            page.screenshot(path=screenshot_path, full_page=True)
            browser.close()
        print("Screenshot captured.")

class Boto3Collector:
    def __init__(self):
        self.cloudtrail_client = boto3.client('cloudtrail', region_name=DEFAULT_REGION)
        self.iam_client = boto3.client('iam', region_name=DEFAULT_REGION)
        self.ec2_client = boto3.client('ec2', region_name=DEFAULT_REGION)
        self.logs_client = boto3.client('logs', region_name=DEFAULT_REGION)

    def collect_iam_role_changes(self, start_time: datetime.datetime, end_time: datetime.datetime, evidence_dir: str):
        os.makedirs(evidence_dir, exist_ok=True)
        output_file = os.path.join(evidence_dir, "CloudTrail_IAM_role_changes.json")
        print(f"Collecting IAM role changes from CloudTrail. Saving to {output_file}")
        events = []
        next_token = None
        while True:
            kwargs = {
                "StartTime": start_time,
                "EndTime": end_time,
                "LookupAttributes": [
                    {
                        "AttributeKey": "EventSource",
                        "AttributeValue": "iam.amazonaws.com"
                    }
                ],
                "MaxResults": 50
            }
            if next_token:
                kwargs["NextToken"] = next_token
            response = self.cloudtrail_client.lookup_events(**kwargs)
            events.extend(response.get("Events", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
            time.sleep(0.2)
        with open(output_file, "w") as f:
            json.dump(events, f, default=str, indent=4)
        print(f"Collected {len(events)} IAM role change events.")

    def collect_iam_access_review(self, evidence_dir: str):
        os.makedirs(evidence_dir, exist_ok=True)
        print("Generating IAM credential report.")
        self.iam_client.generate_credential_report()
        time.sleep(5)  # Allow some time for the report to be generated
        response = self.iam_client.get_credential_report()
        report_content = response['Content'].decode('utf-8')
        output_file = os.path.join(evidence_dir, "IAM_credential_report.csv")
        with open(output_file, "w") as f:
            f.write(report_content)
        print(f"IAM Credential report saved to {output_file}")

    def collect_cloudtrail_logs(self, start_time: datetime.datetime, end_time: datetime.datetime, evidence_dir: str):
        os.makedirs(evidence_dir, exist_ok=True)
        output_file = os.path.join(evidence_dir, "CloudTrail_logs.json")
        print(f"Collecting generic CloudTrail logs from {start_time} to {end_time}. Saving to {output_file}")
        events = []
        next_token = None
        while True:
            kwargs = {
                "StartTime": start_time,
                "EndTime": end_time,
                "MaxResults": 50
            }
            if next_token:
                kwargs["NextToken"] = next_token
            response = self.cloudtrail_client.lookup_events(**kwargs)
            events.extend(response.get("Events", []))
            next_token = response.get("NextToken")
            if not next_token:
                break
            time.sleep(0.2)
        with open(output_file, "w") as f:
            json.dump(events, f, default=str, indent=4)
        print(f"Collected {len(events)} CloudTrail events.")

    def collect_vpc_flow_logs(self, vpc_id: str, evidence_dir: str):
        os.makedirs(evidence_dir, exist_ok=True)
        output_file_config = os.path.join(evidence_dir, "VPC_flow_logs_config.json")
        print(f"Collecting VPC Flow Logs configuration for VPC {vpc_id}. Saving to {output_file_config}")
        response = self.ec2_client.describe_flow_logs(
            Filters=[
                {"Name": "resource-id", "Values": [vpc_id]}
            ]
        )
        flow_logs = response.get("FlowLogs", [])
        with open(output_file_config, "w") as f:
            json.dump(flow_logs, f, default=str, indent=4)
        print(f"Collected {len(flow_logs)} flow log configurations.")
        
        # Optionally fetch sample CloudWatch logs if the flow logs are delivered there.
        if flow_logs:
            for flow_log in flow_logs:
                log_group_name = flow_log.get("LogGroupName")
                if log_group_name:
                    print(f"Fetching sample logs from CloudWatch log group: {log_group_name}")
                    sample_logs = self._fetch_cloudwatch_logs(log_group_name)
                    output_file_logs = os.path.join(evidence_dir, f"{log_group_name}_sample_logs.txt")
                    with open(output_file_logs, "w") as f:
                        f.write(sample_logs)
                    print(f"Sample logs saved to {output_file_logs}")

    def _fetch_cloudwatch_logs(self, log_group_name: str, limit=20):
        try:
            response = self.logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=1
            )
            log_streams = response.get("logStreams", [])
            if not log_streams:
                return "No log streams found."
            log_stream_name = log_streams[0]["logStreamName"]
            events_response = self.logs_client.get_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                limit=limit,
                startFromHead=False
            )
            events = events_response.get("events", [])
            logs_text = "\n".join([event.get("message", "") for event in events])
            return logs_text
        except Exception as e:
            return f"Error fetching logs: {e}"
