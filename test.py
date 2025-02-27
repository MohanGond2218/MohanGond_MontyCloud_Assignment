import json
import base64
import boto3
import pytest
import time
from moto import mock_s3, mock_dynamodb2
from lambda_function import upload_image, list_images, view_image, delete_image  # Import functions being tested


# Helper function to set up S3 & DynamoDB in each test
def setup_aws_services():
    """Initialize LocalStack S3 and DynamoDB"""
    s3 = boto3.client("s3")
    dynamodb = boto3.resource("dynamodb")

    # Create S3 bucket
    s3.create_bucket(Bucket="instagram-images")

    # Create DynamoDB table
    dynamodb.create_table(
        TableName="ImagesMetadata",
        KeySchema=[{"AttributeName": "image_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "image_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST"
    )

    # Ensure table is active
    time.sleep(2)
    return s3, dynamodb


@mock_s3
@mock_dynamodb2
def test_upload_image():
    """Test uploading an image with metadata"""
    setup_aws_services()

    event = {
        "body": json.dumps(
            {"image": base64.b64encode(b"test_image").decode(), "metadata": {"user": "test_user"}}
        )
    }
    
    response = upload_image(event, None)
    assert response["statusCode"] == 200
    assert "image_id" in json.loads(response["body"])


@mock_s3
@mock_dynamodb2
def test_list_images():
    """Test listing images with filter support"""
    setup_aws_services()

    # Upload test image first
    upload_event = {
        "body": json.dumps(
            {"image": base64.b64encode(b"test_image").decode(), "metadata": {"user": "test_user"}}
        )
    }
    upload_image(upload_event, None)

    # List images
    event = {"queryStringParameters": {"user": "test_user"}}
    response = list_images(event, None)
    images = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert len(images) > 0
    assert images[0]["user"] == "test_user"


@mock_s3
@mock_dynamodb2
def test_view_image():
    """Test generating a pre-signed URL for an image"""
    setup_aws_services()

    # Upload test image first
    upload_event = {
        "body": json.dumps(
            {"image": base64.b64encode(b"test_image").decode(), "metadata": {"user": "test_user"}}
        )
    }
    upload_response = upload_image(upload_event, None)
    image_id = json.loads(upload_response["body"])["image_id"]

    # View image
    event = {"pathParameters": {"image_id": image_id}}
    response = view_image(event, None)
    
    assert response["statusCode"] == 200
    assert "url" in json.loads(response["body"])


@mock_s3
@mock_dynamodb2
def test_delete_image():
    """Test deleting an image from S3 and DynamoDB"""
    setup_aws_services()

    # Upload test image first
    upload_event = {
        "body": json.dumps(
            {"image": base64.b64encode(b"test_image").decode(), "metadata": {"user": "test_user"}}
        )
    }
    upload_response = upload_image(upload_event, None)
    image_id = json.loads(upload_response["body"])["image_id"]

    # Delete image
    event = {"pathParameters": {"image_id": image_id}}
    response = delete_image(event, None)
    
    assert response["statusCode"] == 200
    assert "Image deleted successfully" in json.loads(response["body"])
