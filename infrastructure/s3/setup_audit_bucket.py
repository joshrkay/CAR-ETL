"""Script to create S3 bucket with Object Lock for audit logs."""
import sys
import os
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config.audit_config import get_audit_config


def create_audit_bucket() -> bool:
    """Create S3 bucket with Object Lock enabled in Compliance Mode.
    
    Returns:
        True if bucket was created successfully, False otherwise.
    """
    config = get_audit_config()
    
    # Create S3 client
    if config.aws_access_key_id and config.aws_secret_access_key:
        s3_client = boto3.client(
            's3',
            region_name=config.audit_s3_region,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key
        )
    else:
        s3_client = boto3.client('s3', region_name=config.audit_s3_region)
    
    bucket_name = config.audit_s3_bucket
    
    try:
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"Bucket {bucket_name} already exists")
            
            # Verify Object Lock is enabled
            try:
                response = s3_client.get_object_lock_configuration(Bucket=bucket_name)
                if response.get('ObjectLockConfiguration'):
                    print("Object Lock is already enabled")
                    return True
                else:
                    print("ERROR: Bucket exists but Object Lock is not enabled")
                    print("Object Lock cannot be enabled on existing buckets")
                    return False
            except ClientError as e:
                if e.response['Error']['Code'] == 'ObjectLockConfigurationNotFoundError':
                    print("ERROR: Bucket exists but Object Lock is not enabled")
                    print("Object Lock cannot be enabled on existing buckets")
                    return False
                raise
            
        except ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise
            
            # Create bucket with Object Lock enabled
            print(f"Creating bucket {bucket_name} with Object Lock...")
            
            # Create bucket (must be in same region as client)
            if config.audit_s3_region == 'us-east-1':
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': config.audit_s3_region
                    }
                )
            
            # Enable versioning (required for Object Lock)
            print("Enabling versioning...")
            s3_client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            
            # Enable Object Lock
            print("Enabling Object Lock...")
            s3_client.put_object_lock_configuration(
                Bucket=bucket_name,
                ObjectLockConfiguration={
                    'ObjectLockEnabled': 'Enabled',
                    'Rule': {
                        'DefaultRetention': {
                            'Mode': 'COMPLIANCE',
                            'Days': config.audit_retention_years * 365
                        }
                    }
                }
            )
            
            # Block public access
            print("Blocking public access...")
            s3_client.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            
            # Enable encryption
            print("Enabling server-side encryption...")
            s3_client.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    'Rules': [{
                        'ApplyServerSideEncryptionByDefault': {
                            'SSEAlgorithm': 'AES256'
                        }
                    }]
                }
            )
            
            print(f"✅ Successfully created bucket {bucket_name} with Object Lock")
            print(f"   Region: {config.audit_s3_region}")
            print(f"   Retention: {config.audit_retention_years} years (Compliance Mode)")
            return True
            
    except ClientError as e:
        print(f"❌ Error creating bucket: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def verify_bucket_configuration() -> bool:
    """Verify bucket has correct Object Lock configuration.
    
    Returns:
        True if configuration is correct, False otherwise.
    """
    config = get_audit_config()
    
    if config.aws_access_key_id and config.aws_secret_access_key:
        s3_client = boto3.client(
            's3',
            region_name=config.audit_s3_region,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key
        )
    else:
        s3_client = boto3.client('s3', region_name=config.audit_s3_region)
    
    bucket_name = config.audit_s3_bucket
    
    try:
        # Check Object Lock configuration
        response = s3_client.get_object_lock_configuration(Bucket=bucket_name)
        config_obj = response.get('ObjectLockConfiguration')
        
        if not config_obj:
            print("❌ Object Lock is not enabled")
            return False
        
        if config_obj.get('ObjectLockEnabled') != 'Enabled':
            print("❌ Object Lock is not enabled")
            return False
        
        rule = config_obj.get('Rule', {}).get('DefaultRetention', {})
        if rule.get('Mode') != 'COMPLIANCE':
            print(f"❌ Object Lock mode is {rule.get('Mode')}, expected COMPLIANCE")
            return False
        
        print("✅ Bucket configuration verified:")
        print(f"   Object Lock: Enabled (Compliance Mode)")
        print(f"   Retention: {rule.get('Days', 0) / 365:.1f} years")
        return True
        
    except ClientError as e:
        print(f"❌ Error verifying bucket: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup S3 bucket for audit logs")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing bucket configuration"
    )
    
    args = parser.parse_args()
    
    if args.verify:
        success = verify_bucket_configuration()
    else:
        success = create_audit_bucket()
    
    sys.exit(0 if success else 1)
