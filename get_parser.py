import pandas as pd

from .aws_parser import main as aws_parser
from .azure_parser import main as azure_parser
from .gcp_parser import main as gcp_parser


def get_csv_parser(file_or_filename):
    """
    Check whether the CSV file belongs to AWS, GCP or Azure based on its header.

    Args:
        file_or_filename (Union[file, str]): Either a file object or a filename containing the CSV data.

    Returns:
        function: Either aws_parser or azure_parser depending on the header of the CSV file.
    """

    if isinstance(file_or_filename, str):
        with open(file_or_filename, "r") as file:
            header = pd.read_csv(file, nrows=0).columns
            file.seek(0)  # Reset file pointer to beginning of file
    else:
        file = file_or_filename.stream
        if isinstance(file, bytes):
            file = file.decode("utf-8")
        header = pd.read_csv(file, nrows=0).columns
        file_or_filename.stream.seek(0)  # Reset file pointer to beginning of file

    # Check if the required columns for AWS are present in the header
    if all(
        col in header
        for col in [
            "RecordType",
            "LinkedAccountId",
            "UsageStartDate",
            "UsageType",
            "UsageQuantity",
        ]
    ):
        return "AWS Billing Summary", aws_parser

    # Check if the required columns for Azure are present in the header
    if all(
        col in header
        for col in [
            "billingPeriodStartDate",
            "unitOfMeasure",
            "product",
            "quantity",
            "meterCategory",
            "invoiceSectionName",
            "additionalInfo",
        ]
    ):
        return "Azure Billing Summary", azure_parser

    # Check if the required columns for GCP are present in the header
    if all(
        col in header
        for col in [
            "Usage amount",
            "SKU description",
            "Usage unit",
            "Usage start date",
            "Usage end date",
            "Project ID",
        ]
    ):
        return "GCP Billing Summary", gcp_parser

    # If neither set of required columns are present, return None
    return "", None
