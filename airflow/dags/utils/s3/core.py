import os
import boto3
from botocore.exceptions import ClientError
import json
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

