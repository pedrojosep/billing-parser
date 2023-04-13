import calendar
import json
from typing import Tuple

import click
import numpy as np
import pandas as pd
from rich.console import Console

from .utils import write_excel


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
    Parse a billing CSV file into two pandas DataFrames.

    Args:
        filename (str): The name of the CSV file.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: A tuple containing the original DataFrame and the aggregated DataFrame.
    """
    # Read the billing CSV file into a pandas DataFrame
    df = pd.read_csv(filename)

    # Calculate number of hours in the month
    df["billingPeriodStartDate"] = pd.to_datetime(df["billingPeriodStartDate"])
    df["Month"] = df["billingPeriodStartDate"].dt.month
    df["Year"] = df["billingPeriodStartDate"].dt.year
    df["NumDaysInMonth"] = df.apply(
        lambda row: calendar.monthrange(row["Year"], row["Month"])[1], axis=1
    )
    df["NumHoursInMonth"] = df["NumDaysInMonth"] * 24
    df["NumSecondsInMonth"] = df["NumHoursInMonth"] * 3600

    # Extract the number of virtual CPUs from the additionalInfo column using the extract_vcpu function
    df = df.assign(instanceVCPU=df.apply(extract_vcpu, axis=1))

    # Calculate the monthly usage based on the unit of measure (hours)
    # and add it as a new column to the DataFrame
    df = df.assign(
        monthlyUsage=np.where(
            df["unitOfMeasure"] == "1 Hour", df["quantity"] / df["NumHoursInMonth"], 0
        )
    )

    # Calculate the total number of VMs based on the number of virtual CPUs and the monthly usage
    # and add it as a new column to the DataFrame
    df = df.assign(VMs=df["instanceVCPU"] * df["monthlyUsage"])

    # Calculate the total number of Functions based on the quantity (in seconds)
    # and add it as a new column to the DataFrame
    df = df.assign(
        functions=np.where(
            df["product"] == "Functions", df["quantity"] / df["NumSecondsInMonth"], 0
        )
    )

    # Calculate the total number of App Services based on the quantity (in minutes)
    # and add it as a new column to the DataFrame
    df = df.assign(
        AppServices=np.where(
            df["meterCategory"] == "Azure App Service",
            df["quantity"] / df["NumHoursInMonth"],
            0,
        )
    )

    # Group the DataFrame by invoiceSectionName and sum the total number of VMs, Functions, and App Services
    # to get the aggregated DataFrame
    total_df = df.groupby("invoiceSectionName")[
        ["VMs", "functions", "AppServices"]
    ].sum()

    # Reset the index and rename the first column
    total_df = total_df.reset_index().rename(
        columns={"invoiceSectionName": "Section Name"}
    )

    # Calculate totals for each column
    total_vms = total_df["VMs"].sum()
    total_functions = total_df["functions"].sum()
    total_apps_service = total_df["AppServices"].sum()

    # Add the total row to total_df
    total_row = pd.DataFrame(
        {
            "Section Name": ["Total"],
            "VMs": [total_vms],
            "functions": [total_functions],
            "AppServices": [total_apps_service],
        },
    )
    total_df = pd.concat([total_df, total_row])

    # Return both the original DataFrame and the aggregated DataFrame as a tuple
    return df, total_df


def main(billing_csv: str = None, write_file: bool = False) -> None:
    """
    The main function of the script. Parses the billing CSV file and writes the results to an Excel file.

    Args:
        billing_csv (str): The path to the billing CSV file.
    """
    print("Processing Azure csv")

    df, total_df = parse_billing_csv(billing_csv)

    if write_file:
        # Use Rich to display the dataframe
        console = Console()
        console.print(total_df, justify="left")

        write_excel(df, total_df)

    return total_df


@click.command()
@click.argument("billing_csv", type=click.Path(exists=True))
def command(billing_csv: str = None) -> None:
    main(billing_csv, True)


if __name__ == "__main__":
    command()
