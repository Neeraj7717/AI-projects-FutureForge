import os
import boto3
from dotenv import load_dotenv

load_dotenv()

ACCESS_KEY = os.environ.get('ACCESS_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')

def download_from_s3_bucket(bucket_name, cloud_path, local_store_path):
    """
    Download the latest file from an S3 bucket and store it locally.

    Parameters:
    - bucket_name (str): The name of the S3 bucket.
    - cloud_path (str): The path in the S3 bucket.
    - local_store_path (str): The local directory where the file will be stored.

    Returns:
    - str: Local path of the downloaded file or "failed" if unsuccessful.
    """
    try:
        # Create an S3 session
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY
        )
        s3 = session.resource("s3")
        bucket = s3.Bucket(bucket_name)

        # List files, sort by last modified, and get the latest file
        fileobjs = list(bucket.objects.filter(Prefix=cloud_path))
        get_last_modified = lambda obj: obj.last_modified
        file_last_added = [
            obj.key for obj in sorted(fileobjs, key=get_last_modified, reverse=True)
        ][0]

        # Download the latest file
        s3.Bucket(bucket_name).download_file(
            Filename=local_store_path, Key=file_last_added
        )

        return local_store_path
    except Exception as e:
        return e


def upload_to_s3_bucket(bucket_name, local_filename, cloud_path, filename):
    """
    Upload a file to an S3 bucket.

    Parameters:
    - bucket_name (str): The name of the S3 bucket.
    - local_filename (str): The local file to upload.
    - cloud_path (str): The path in the S3 bucket.
    - filename (str): The name to be used in the S3 bucket.

    Returns:
    - str: URL of the uploaded file or "url" if unsuccessful.
    """
    try:
        # Create an S3 session
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY
        )
        s3 = session.resource("s3")

        # Upload the file to S3
        s3.meta.client.upload_file(
            local_filename, bucket_name, cloud_path + str(filename)
        )

        # Generate and return the URL of the uploaded file
        url = (
            f"https://{os.environ.get('cdn_link')}.eizen.ai/{cloud_path}{filename}"
        )
        
        return url
    except Exception as e:
        return "url"


def download_folder_from_s3_bucket(bucket_name, cloud_path, local_store_path):
    """
    Download all files from a folder in an S3 bucket and store them locally.

    Parameters:
    - bucket_name (str): The name of the S3 bucket.
    - cloud_path (str): The path in the S3 bucket.
    - local_store_path (str): The local directory where the files will be stored.

    Returns:
    - str: Local path of the downloaded files or "failed" if unsuccessful.
    """
    try:
        # Create an S3 session
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY
        )
        s3 = session.resource("s3")
        bucket = s3.Bucket(bucket_name)

        # List files in the specified path
        file_objs = list(bucket.objects.filter(Prefix=cloud_path))

        # Download each file in the path
        for obj in file_objs:
            if obj.key.endswith("/"):
                continue

            # Construct local file path and create directories if needed
            local_file_path = os.path.join(
                local_store_path, os.path.relpath(obj.key, cloud_path)
            )
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            s3.Bucket(bucket_name).download_file(obj.key, local_file_path)

        return local_store_path
    except Exception as e:
        return "failed"


def upload_folder_to_s3_bucket(bucket_name, local_directory, cloud_path):
    """
    Upload all files from a local directory to a folder in an S3 bucket.

    Parameters:
    - bucket_name (str): The name of the S3 bucket.
    - local_directory (str): The local directory containing files to upload.
    - cloud_path (str): The path in the S3 bucket.

    Returns:
    - list: List of keys of the uploaded files or an empty list if unsuccessful.
    """
    try:
        # Create an S3 session
        session = boto3.Session(
            aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY
        )
        s3 = session.resource("s3")
        bucket = s3.Bucket(bucket_name)
        uploaded_keys = []

        # Iterate over local files and upload them to S3
        for root, dirs, files in os.walk(local_directory):
            for file in files:
                local_path = os.path.join(root, file)
                s3_key = os.path.join(
                    cloud_path, os.path.relpath(local_path, local_directory)
                )

                # Upload file to S3
                bucket.upload_file(Filename=local_path, Key=s3_key)
                uploaded_keys.append(s3_key)

        return uploaded_keys
    except Exception as e:
        return []


# # Example usage of download_from_s3_bucket
# bucket_name = ''
# cloud_path = ''
# local_store_path = ''
# downloaded_file = download_from_s3_bucket(bucket_name, cloud_path, local_store_path)
# print(f"Downloaded file: {downloaded_file}")

# # # Example usage of upload_to_s3
# bucket_name = ''
# local_filename = ''
# cloud_path = ''
# filename = ''
# uploaded_url = upload_to_s3_bucket(bucket_name, local_filename, cloud_path, filename)
# print(f"Uploaded URL: {uploaded_url}")

# # Example usage of download_folder_from_s3_bucket
# bucket_name = 'kcbigbucket'    
# cloud_path = 'checkpoints'
# local_store_path_folder = 'checkpoints'
# downloaded_folder = download_folder_from_s3_bucket(bucket_name, cloud_path, local_store_path_folder)
# print(f"Downloaded folder: {downloaded_folder}")

# # Example usage of upload_folder_to_s3_bucket
# bucket_name = ''
# local_directory_to_upload = ''
# cloud_path_folder = ''
# uploaded_keys = upload_folder_to_s3_bucket(bucket_name, local_directory_to_upload, cloud_path_folder)
# print(f"Uploaded keys: {uploaded_keys}")
