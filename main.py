import calendar
import json

import boto3
import click
import numpy as np
import pandas as pd
from rich.console import Console


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
        save_instance_types_to_cache(instance_types)

    return instance_types


def load_instance_types_from_cache(
    cache_file_path: str = "instance_types_cache.json",
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
    session = boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )
    ec2 = session.client("ec2")

    instance_types = []
    response = ec2.describe_instance_types(
        DryRun=False,
        Filters=[
            {
                "Name": "processor-info.supported-architecture",
                "Values": ["x86_64"],
            },
        ],
        MaxResults=100,
    )
    instance_types.extend(response["InstanceTypes"])
    while "NextToken" in response:
        response = ec2.describe_instance_types(
            DryRun=False,
            Filters=[
                {
                    "Name": "processor-info.supported-architecture",
                    "Values": ["x86_64"],
                },
            ],
            MaxResults=100,
            NextToken=response["NextToken"],
        )
        instance_types.extend(response["InstanceTypes"])

    return {i["InstanceType"]: i["VCpuInfo"]["DefaultVCpus"] for i in instance_types}


def save_instance_types_to_cache(
    instance_types, cache_file_path: str = "instance_types_cache.json"
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
    df = df.dropna(subset=["LinkedAccountId"])

    # Calculate number of hours in the month
    df["UsageStartDate"] = pd.to_datetime(df["UsageStartDate"])
    df["Month"] = df["UsageStartDate"].dt.month
    df["Year"] = df["UsageStartDate"].dt.year
    df["NumDaysInMonth"] = df.apply(
        lambda row: calendar.monthrange(row["Year"], row["Month"])[1], axis=1
    )
    df["NumHoursInMonth"] = df["NumDaysInMonth"] * 24

    # Calculate Total VMs
    df["InstanceName"] = df["UsageType"].apply(lambda x: str(x).split(":")[-1])
    df["InstanceVCPU"] = df["InstanceName"].apply(lambda x: instance_types.get(x))
    df["numInstances"] = np.where(
        df["InstanceVCPU"].notnull(),
        df["UsageQuantity"] / df["NumHoursInMonth"],
        np.nan,
    )
    df["TotalEC2"] = df["InstanceVCPU"] * df["numInstances"]

    # Calculate Total Lambda
    df["TotalLambda"] = 0
    lambda_mask = (df["ProductCode"] == "AWSLambda") & (
        df["UsageType"].str.contains("Lambda-GB-Second")
    )
    df.loc[lambda_mask, "TotalLambda"] = df["UsageQuantity"] / (
        3600 * 1024 * df["NumHoursInMonth"]
    )

    # Calculate Total Fargate
    df["TotalFargate"] = 0
    fargate_mask = (df["ProductCode"] == "AmazonECS") & (
        df["UsageType"].str.contains("Fargate-vCPU-Hours:perCPU")
    )
    df.loc[fargate_mask, "TotalFargate"] = df["UsageQuantity"] / df["NumHoursInMonth"]

    # Group by LinkedAccountId and sum usage data
    total_df = df.groupby("LinkedAccountId")[
        ["TotalEC2", "TotalLambda", "TotalFargate"]
    ].sum()

    # Calculate totals for each column
    total_vms = total_df["TotalEC2"].sum()
    total_lambda = total_df["TotalLambda"].sum()
    total_fargate = total_df["TotalFargate"].sum()

    # Add the total row to total_df
    total_row = pd.DataFrame(
        {
            "TotalEC2": [total_vms],
            "TotalLambda": [total_lambda],
            "TotalFargate": [total_fargate],
        },
        index=["Total"],
    )
    total_df = pd.concat([total_df, total_row])

    return df, total_df


def write_excel(df, total_df):
    """
    Write a pandas DataFrame to an Excel file with two sheets: Detail and Total.

    :param df: The pandas DataFrame to write to the Excel file.
    :param total_df: The pandas DataFrame containing the total usage data to write to the Total sheet.
    """
    print("Saving results into output.xlsx")
    writer = pd.ExcelWriter("output.xlsx", engine="xlsxwriter")
    df.to_excel(writer, sheet_name="Detail")
    total_df.to_excel(writer, sheet_name="Total")
    writer.close()


@click.command()
@click.argument("billing_csv", type=click.Path(exists=True))
@click.option(
    "--use-cache/--no-cache",
    default=True,
    help="Enable or disable use of cache (default: enabled)",
)
@click.option(
    "--access-key-id",
    type=str,
    default=None,
    help="AWS access key ID for API authentication",
)
@click.option(
    "--secret-access-key",
    type=str,
    default=None,
    help="AWS secret access key for API authentication",
)
@click.option(
    "--region",
    type=str,
    default=None,
    help="AWS region name for retrieving EC2 instance types",
)
def main(
    billing_csv: str = None,
    use_cache: bool = True,
    access_key_id: str = None,
    secret_access_key: str = None,
    region: str = None,
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

    # Parse billing CSV and calculate total usage
    df, total_df = parse_billing_csv(billing_csv, instance_types)

    # Use Rich to display the dataframe
    console = Console()
    console.print(total_df, justify="left")

    # Write parsed data and total usage data to Excel file
    write_excel(df, total_df)


if __name__ == "__main__":
    main()
