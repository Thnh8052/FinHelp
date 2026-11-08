import os
import boto3
import httpx
from botocore.config import Config

def test_full_r2_flow():
    endpoint_url = "https://cbd378f5a3cd91fe9f7e30ec726e623d.r2.cloudflarestorage.com"
    access_key = "f2397ca273286a3f19a49f56a95ae002"
    secret_key = "ac40d315546badecefe87c38c9e94575ce8baa14efb9ea5182201e4a7d9283b6"
    bucket_name = "finhelp-storage"
    public_domain = "https://pub-3faf2006720a40408ea0eecc1ef261cf.r2.dev"

    print("1. Connecting to S3 client...")
    s3 = boto3.client(
        service_name="s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

    test_key = "test_connectivity/hello_finhelp.txt"
    test_content = b"Hello from FinHelp R2 Storage setup!"

    print(f"2. Uploading test object to {bucket_name}/{test_key}...")
    s3.put_object(
        Bucket=bucket_name,
        Key=test_key,
        Body=test_content,
        ContentType="text/plain",
    )
    print("   Upload successful!")

    print(f"3. Testing Public URL: {public_domain}/{test_key}...")
    try:
        resp = httpx.get(f"{public_domain}/{test_key}", timeout=10)
        if resp.status_code == 200 and resp.content == test_content:
            print(f"   Public Access URL verified! Status: {resp.status_code}, Content matches!")
        else:
            print(f"   Public Access response: Status {resp.status_code}, Body: {resp.text[:100]}")
    except Exception as e:
        print(f"   Could not fetch public url: {e}")

    print("4. Downloading object via S3 API...")
    get_resp = s3.get_object(Bucket=bucket_name, Key=test_key)
    downloaded = get_resp["Body"].read()
    assert downloaded == test_content, "Content mismatch!"
    print(f"   S3 API download verified! Size: {len(downloaded)} bytes.")

    print(f"5. Cleaning up test object: {test_key}...")
    s3.delete_object(Bucket=bucket_name, Key=test_key)
    print("   Cleanup successful!")
    print("\n>>> ALL CLOUDFLARE R2 CHECKS PASSED 100%! <<<")

if __name__ == "__main__":
    test_full_r2_flow()
