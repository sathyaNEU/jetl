import os
import boto3
from botocore.exceptions import ClientError
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()

def get_s3_client():
    try:
        s3_client = boto3.client(
        's3', 
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"), 
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION")  
        )
        return s3_client
    except:
        return -1
    

def upload_to_s3(data, s3_key):
    """Upload JSON data to S3"""
    BUCKET_NAME = os.getenv('BUCKET_NAME')
    print('core.py', BUCKET_NAME)
    try:
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(data, indent=4, ensure_ascii=False),
            ContentType='application/json'
        )
        return True
    except ClientError as e:
        return False

def upload_csv_to_s3(data, s3_key, content_type='text/csv'):
    """Upload CSV data to S3"""
    BUCKET_NAME = os.getenv('BUCKET_NAME')
    try:
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=data, 
            ContentType=content_type
        )
        return True
    except ClientError as e:
        return False


def send_job_completion_notification(s3_key, job_start_time, role_name, jobs_count):
    """Send SNS notification when job scraping is completed"""
    SNS_TOPIC_ARN = "arn:aws:sns:us-east-2:374834463497:jobs"
    BUCKET_NAME = os.getenv('BUCKET_NAME')
    
    try:
        # Create SNS client
        sns_client = boto3.client(
            'sns',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION")
        )
        
        # Construct the fully qualified S3 URL
        s3_url = f"https://{BUCKET_NAME}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_key}"
        
        # Prepare the message
        message = {
            "job_completion_status": "SUCCESS",
            "role": role_name,
            "job_start_time": job_start_time,
            "job_completion_time": datetime.now(ZoneInfo("America/New_York")).strftime('%Y-%m-%d %H:%M:%S'),
            "s3_file_url": s3_url,
            "s3_key": s3_key,
            "jobs_scraped_count": jobs_count,
            "bucket_name": BUCKET_NAME
        }
        
        # Email subject
        subject = f"Job Scraping Complete - {role_name} ({jobs_count} jobs)"
        
        # Send notification
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message, indent=2),
            Subject=subject
        )
        
        print(f"SNS notification sent successfully. MessageId: {response['MessageId']}")
        return True
        
    except ClientError as e:
        print(f"Failed to send SNS notification: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error sending SNS notification: {e}")
        return False