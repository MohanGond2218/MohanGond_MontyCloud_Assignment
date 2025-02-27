import boto3
import uuid
import json
import base64
import os
import pytest
from botocore.exceptions import NoCredentialsError

# Setup AWS clients (using LocalStack endpoint for local development)
s3 = boto3.client('s3', endpoint_url=os.getenv("LOCALSTACK_ENDPOINT"))
dynamodb = boto3.resource('dynamodb', endpoint_url=os.getenv("LOCALSTACK_ENDPOINT"))

table_name = "ImagesMetadata"
bucket_name = "instagram-images"
table = dynamodb.Table(table_name)

def upload_image(event, context):
    """ Upload image and store metadata in DynamoDB """
    body = json.loads(event['body'])
    image_data = base64.b64decode(body['image'])
    image_id = str(uuid.uuid4())
    image_key = f"{image_id}.jpg"
    metadata = body['metadata']
    
    try:
        # Upload image to S3
        s3.put_object(Bucket=bucket_name, Key=image_key, Body=image_data)
        
        # Store metadata in DynamoDB
        metadata['image_id'] = image_id
        metadata['image_key'] = image_key
        table.put_item(Item=metadata)
        
        return {"statusCode": 200, "body": json.dumps({"message": "Image uploaded successfully", "image_id": image_id})}
    except NoCredentialsError:
        return {"statusCode": 500, "body": json.dumps({"error": "AWS credentials not found"})}

def list_images(event, context):
    """ List images with filters """
    filters = event.get("queryStringParameters", {})
    response = table.scan()
    
    images = [item for item in response['Items'] if all(item.get(k) == v for k, v in filters.items())]
    return {"statusCode": 200, "body": json.dumps(images)}

def view_image(event, context):
    """ Generate pre-signed URL to view/download image """
    image_id = event['pathParameters']['image_id']
    response = table.get_item(Key={"image_id": image_id})
    
    if 'Item' not in response:
        return {"statusCode": 404, "body": json.dumps({"error": "Image not found"})}
    
    image_key = response['Item']['image_key']
    url = s3.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': image_key}, ExpiresIn=3600)
    return {"statusCode": 200, "body": json.dumps({"url": url})}

def delete_image(event, context):
    """ Delete image from S3 and DynamoDB """
    image_id = event['pathParameters']['image_id']
    response = table.get_item(Key={"image_id": image_id})
    
    if 'Item' not in response:
        return {"statusCode": 404, "body": json.dumps({"error": "Image not found"})}
    
    image_key = response['Item']['image_key']
    
    # Delete from S3
    s3.delete_object(Bucket=bucket_name, Key=image_key)
    
    # Delete from DynamoDB
    table.delete_item(Key={"image_id": image_id})
    
    return {"statusCode": 200, "body": json.dumps({"message": "Image deleted successfully"})}

# API Gateway routing
api_routes = {
    "POST /upload": upload_image,
    "GET /images": list_images,
    "GET /image/{image_id}": view_image,
    "DELETE /image/{image_id}": delete_image
}

def lambda_handler(event, context):
    """ Main Lambda function handler """
    route_key = f"{event['httpMethod']} {event['resource']}"
    if route_key in api_routes:
        return api_routes[route_key](event, context)
    return {"statusCode": 404, "body": json.dumps({"error": "Route not found"})}
