import calendar
import json

import boto3
import botocore
import click
import numpy as np
import pandas as pd

DEFAULT_CACHE_FILE_PATH = "parsers/cache/instance_types_cache.json"


def load_aws_instance_types(
    access_key_id=None,
    secret_access_key=None,
    region=None,
    use_cache=True,
):
    """
    Load a dictionary of AWS EC2 instance types with their default number of vCPUs.

    :param access_key_id: Optional AWS access key ID to authenticate the API request.
    :param secret_access_key: Optional AWS secret access key to authenticate the API request.
    :param region: Optional AWS region name to retrieve the instance types from.
    :param use_cache: Optional boolean flag to enable or disable the cache.

    :return: A dictionary of EC2 instance types with their default number of vCPUs.
    """
    if use_cache:
        instance_types = load_instance_types_from_cache()
    else:
        instance_types = load_instance_types_from_api(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            region=region,
        )
        if instance_types:
            save_instance_types_to_cache(instance_types)

    return instance_types


def load_instance_types_from_cache(
    cache_file_path: str = DEFAULT_CACHE_FILE_PATH,
) -> dict:
    """
    Load instance types dictionary from the cache file.

    :return: A dictionary of EC2 instance types with their default number of vCPUs.
    """
    try:
        with open(cache_file_path, "r") as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}

    return cache.get("instance_types", {})


def describe_instance_types(ec2, next_token=None):
    """
    Helper function to describe EC2 instance types.
    :param ec2: EC2 client object.
    :param next_token: Optional token to retrieve the next page of results.
    :return: A list of EC2 instance types with their default number of vCPUs.
    """
    filters = [{"Name": "processor-info.supported-architecture", "Values": ["x86_64"]}]
    kwargs = {"DryRun": False, "Filters": filters, "MaxResults": 100}
    if next_token:
        kwargs["NextToken"] = next_token
    try:
        response = ec2.describe_instance_types(**kwargs)
        instance_types = response["InstanceTypes"]
        if "NextToken" in response:
            instance_types += describe_instance_types(ec2, response["NextToken"])
        return instance_types
    except botocore.exceptions.BotoCoreError as e:
        print(f"Error retrieving instance types: {e}")
        return []


def load_instance_types_from_api(
    access_key_id=None, secret_access_key=None, region=None
):
    """
    Load instance types dictionary from the EC2 API.
    :param access_key_id: Optional AWS access key ID to authenticate the API request.
    :param secret_access_key: Optional AWS secret access key to authenticate the API request.
    :param region: Optional AWS region name to retrieve the instance types from.
    :return: A dictionary of EC2 instance types with their default number of vCPUs.
    """
    try:
        session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )
        ec2 = session.client("ec2")
        instance_types = describe_instance_types(ec2)
        return {
            i["InstanceType"]: i["VCpuInfo"]["DefaultVCpus"] for i in instance_types
        }
    except botocore.exceptions.BotoCoreError as e:
        print(f"Error connecting to boto3: {e}")
        return {}


def save_instance_types_to_cache(
    instance_types, cache_file_path: str = DEFAULT_CACHE_FILE_PATH
) -> None:
    """
    Save instance types dictionary to the cache file.

    :param instance_types: A dictionary of EC2 instance types with their default number of vCPUs.
    """
    cache = {"instance_types": instance_types}
    with open(cache_file_path, "w") as f:
        json.dump(cache, f)


def parse_billing_csv(filename, instance_types):
    """
    Parse an AWS billing CSV file and calculate total usage for EC2, Lambda, and Fargate.

    :param filename: The path to the billing CSV file to parse.
    :param instance_types: A dictionary of EC2 instance types with their default number of vCPUs.

    :return: A tuple containing a pandas DataFrame with the parsed billing data and a pandas
    DataFrame with the total usage data.
    """
    # Load CSV data into a pandas DataFrame
    df = pd.read_csv(filename, dtype={"LinkedAccountId": "str"})

    # Filter out unnecessary rows and columns
    df = df[df["RecordType"] != "AccountTotal"]

    if df["LinkedAccountId"].isnull().all():
        mask = df["RecordType"] == "PayerLineItem"
        df.loc[mask, "LinkedAccountId"] = df.loc[mask, "LinkedAccountId"].fillna(
            df["PayerAccountId"]
        )

    df = df.dropna(subset=["LinkedAccountId"])

    # Calculate number of hours in the month
    df["UsageStartDate"] = pd.to_datetime(df["UsageStartDate"])
    df["Month"] = df["UsageStartDate"].dt.month
    df["Year"] = df["UsageStartDate"].dt.year
    df["NumDaysInMonth"] = df.apply(
        lambda row: calendar.monthrange(row["Year"], row["Month"])[1], axis=1
    )
    df["NumHoursInMonth"] = df["NumDaysInMonth"] * 24

    df["UsageQuantity"] = df["UsageQuantity"].str.replace(",", "").astype(float)

    # Calculate Total VMs
    df["InstanceName"] = df["UsageType"].apply(lambda x: str(x).split(":")[-1])
    df["InstanceVCPU"] = df["InstanceName"].apply(lambda x: instance_types.get(x))
    df.loc[df["InstanceVCPU"].isna(), "InstanceName"] = None
    df["numInstances"] = np.where(
        df["InstanceVCPU"].notnull(),
        df["UsageQuantity"] / df["NumHoursInMonth"],
        np.nan,
    )
    df["EC2"] = df["InstanceVCPU"] * df["numInstances"]

    # Calculate Total Lambda
    df["Lambda"] = 0
    lambda_mask = (df["ProductCode"] == "AWSLambda") & (
        df["UsageType"].str.contains("Lambda-GB-Second")
    )
    df.loc[lambda_mask, "Lambda"] = df["UsageQuantity"] / (
        3600 * 1024 * df["NumHoursInMonth"]
    )

    # Calculate Total Fargate
    df["Fargate"] = 0
    fargate_mask = (df["ProductCode"] == "AmazonECS") & (
        df["UsageType"].str.contains("Fargate-vCPU-Hours:perCPU")
    )
    df.loc[fargate_mask, "Fargate"] = df["UsageQuantity"] / df["NumHoursInMonth"]

    # Group by LinkedAccountId and sum usage data
    total_df = df.groupby("LinkedAccountId")[["EC2", "Lambda", "Fargate"]].sum()

    # Reset the index and rename the first column
    total_df = total_df.reset_index().rename(
        columns={"LinkedAccountId": "Linked Account ID"}
    )

    # Calculate totals for each column
    total_vms = total_df["EC2"].sum()
    total_lambda = total_df["Lambda"].sum()
    total_fargate = total_df["Fargate"].sum()

    # Add the total row to total_df
    total_row = pd.DataFrame(
        {
            "Linked Account ID": ["Total"],
            "EC2": [total_vms],
            "Lambda": [total_lambda],
            "Fargate": [total_fargate],
        },
        index=["Total"],
    )
    total_df = pd.concat([total_df, total_row])

    return df, total_df


def main(
    billing_csv: str = None,
    use_cache: bool = True,
    access_key_id: str = None,
    secret_access_key: str = None,
    region: str = None,
    *args,
    **kwargs,
) -> None:
    """
    Parse an AWS billing CSV file and calculate total usage for EC2, Lambda, and Fargate.
    Write the parsed data and the total usage data to an Excel file with two sheets.

    :param billing_csv: The path to the billing CSV file to parse.
    :param use_cache: Optional boolean flag to enable or disable use of cache (default: enabled).
    :param access_key_id: Optional AWS access key ID for API authentication.
    :param secret_access_key: Optional AWS secret access key for API authentication.
    :param region: Optional AWS region name for retrieving EC2 instance types.
    """
    # Ask user for billing CSV path
    billing_csv = billing_csv or click.prompt(
        "Please provide the path to the AWS billing CSV file",
        type=click.Path(exists=True),
    )

    # Ask user if they want to use the cache
    if use_cache:
        instance_types = load_aws_instance_types(use_cache=True)
    else:
        # Ask for AWS credentials if cache is not used
        access_key_id = access_key_id or click.prompt(
            "AWS Access Key ID", hide_input=False
        )
        secret_access_key = secret_access_key or click.prompt(
            "AWS Secret Access Key", hide_input=True
        )
        region = region or click.prompt("AWS Region Name", type=str)
        instance_types = load_aws_instance_types(
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            region=region,
            use_cache=False,
        )

        # If there was an error retrieving the instance use the cache
        if not instance_types:
            instance_types = load_instance_types_from_cache()

    return parse_billing_csv(billing_csv, instance_types)
