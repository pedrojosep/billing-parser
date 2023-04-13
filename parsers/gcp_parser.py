import json
from typing import Tuple

import pandas as pd


def extract_vcpu(row: pd.Series) -> int:
    """
    Extract the number of virtual CPUs from the additionalInfo column in a pandas DataFrame.

    Args:
        row (pd.Series): A row in the DataFrame.

    Returns:
        int: The number of virtual CPUs in the instance.
    """
    additional_info = row["additionalInfo"]
    try:
        additional_info = json.loads(additional_info)
        return additional_info["VCPUs"]
    except Exception:
        return 0


def parse_billing_csv(filename: str = "") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parses a billing CSV file and returns two pandas DataFrames: one with detailed usage information
    for each line item in the CSV file, and another with the total usage for each project.

    Args:
        filename (str): The filename of the billing CSV file to parse.

    Returns:
        A tuple containing two pandas DataFrames: one with detailed usage information for each line
        item in the CSV file, and another with the total usage for each project.
    """
    # Load the CSV file into a pandas DataFrame
    df = pd.read_csv(filename)

    # Convert the "Usage start date" and "Usage end date" columns to datetime objects
    df["Usage start date"] = pd.to_datetime(df["Usage start date"])
    df["Usage end date"] = pd.to_datetime(df["Usage end date"])

    # Get the minimum value from the "Usage start date" column and the maximum value from the "Usage end date" column
    min_date = df["Usage start date"].min()
    max_date = df["Usage end date"].max()

    # Calculate the number of days between the two dates
    num_days = (max_date - min_date).days + 1

    # Define the number of hours in a month
    hours_per_month = num_days * 24

    df["Usage amount"] = pd.to_numeric(df["Usage amount"], errors="coerce")
    df["SKU description"] = df["SKU description"].astype(str)

    # Add a new column to the DataFrame to calculate the monthly usage based on the "Usage amount"
    # and "Usage unit" columns
    df["monthlyUsage"] = df.apply(
        lambda row: row["Usage amount"] / hours_per_month
        if row["Usage unit"] == "hour"
        else (
            row["Usage amount"] / (hours_per_month * 60 * 60)
            if row["Usage unit"] == "vCPU-second"
            else (
                row["Usage amount"] / (hours_per_month * 60 * 60)
                if row["Usage unit"] == "GHz-second"
                else 0
            )
        ),
        axis=1,
    )

    # Add new columns to the DataFrame to calculate the usage for each service based on the
    # "monthlyUsage", "SKU description", and "Service description" columns
    df["Compute Engine"] = df.apply(
        lambda row: row["monthlyUsage"]
        if (
            "Instance Core" in row["SKU description"]
            and row["Service description"] == "Compute Engine"
        )
        else 0,
        axis=1,
    )

    df["App Engine"] = df.apply(
        lambda row: row["monthlyUsage"]
        if (
            "Instance Core" in row["SKU description"]
            and row["Service description"] == "App Engine"
        )
        else 0,
        axis=1,
    )

    df["Cloud Functions"] = df.apply(
        lambda row: row["monthlyUsage"]
        if (
            "CPU Time" in row["SKU description"]
            and row["Service description"] == "Cloud Functions"
        )
        else 0,
        axis=1,
    )

    # Group the DataFrame by "Project ID" and sum the usage for each service to get the
    # total usage for each project
    total_df = df.groupby("Project ID")[
        ["Compute Engine", "App Engine", "Cloud Functions"]
    ].sum()

    # Reset the index of the grouped DataFrame and rename the "Project ID" column
    total_df = total_df.reset_index().rename(columns={"Project ID": "Project ID"})

    # Calculate the total usage across all projects for each service
    total_compute_engine = total_df["Compute Engine"].sum()
    total_functions = total_df["Cloud Functions"].sum()
    total_apps_engine = total_df["App Engine"].sum()

    # Create a new row in the total DataFrame with the total usage across all projects
    # for each service
    total_row = pd.DataFrame(
        {
            "Project ID": ["Total"],
            "Compute Engine": [total_compute_engine],
            "Cloud Functions": [total_functions],
            "App Engine": [total_apps_engine],
        },
    )

    # Concatenate the total DataFrame with the new row to include the total
    total_df = pd.concat([total_df, total_row])

    return df, total_df


def main(billing_csv: str = None, *args, **kwargs) -> None:
    """
    The main function of the script. Parses the billing CSV file.

    Args:
        billing_csv (str): The path to the billing CSV file.
    """
    return parse_billing_csv(billing_csv)
