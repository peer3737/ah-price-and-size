import boto3
import getpass
from botocore.exceptions import ClientError, ParamValidationError
import tkinter as tk
from tkinter import simpledialog


def client(mfa=False, profile_name='peter'):
    if mfa:
        client = boto3.client('sts')  # Create an STS (Security Token Service) client
        root = tk.Tk()
        root.withdraw()
        root.geometry("300x150")  # Width x Height

        # Prompt for the password
        token = simpledialog.askstring("Password", "Enter your password:", show='*')



        try:
            response = client.get_session_token(
                SerialNumber='arn:aws:iam::101584893836:mfa/google',
                TokenCode=str(token)
            )
        except ClientError as e:
            print("Invalid MFA token")
            return False

        except ParamValidationError as e:
            print("Invalid MFA token format")
            return False
        try:
            credentials = response['Credentials']
            access_key_id = credentials['AccessKeyId']
            secret_access_key = credentials['SecretAccessKey']
            session_token = credentials['SessionToken']

            session = boto3.Session(
                profile_name=profile_name,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                aws_session_token=session_token
            )

            s3 = session.client('s3')
            return s3

        except Exception as e:
            return False
    else:
        try:
            session = boto3.Session(profile_name=profile_name)
            s3 = session.client('s3')
            return s3

        except Exception as e:
            return False
