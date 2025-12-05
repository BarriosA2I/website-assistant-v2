#!/bin/bash
# =============================================================================
# LocalStack S3 Initialization
# =============================================================================

echo "Initializing LocalStack S3..."

# Create video delivery bucket
awslocal s3 mb s3://videoforge-deliveries

# Set bucket policy for public read (for testing)
awslocal s3api put-bucket-policy --bucket videoforge-deliveries --policy '{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::videoforge-deliveries/*"
        }
    ]
}'

# Create sample video for testing
echo "Creating sample video placeholder..."
echo "SAMPLE_VIDEO_CONTENT" | awslocal s3 cp - s3://videoforge-deliveries/videos/test/sample.mp4

echo "LocalStack S3 initialization complete!"
echo "Bucket: videoforge-deliveries"
echo "Endpoint: http://localhost:4566"
