import csv
import click
import aws_parser
import azure_parser


def get_csv_parser(filename):
    """
    Check whether the CSV file belongs to AWS or Azure based on its header.

    Args:
        filename (str): The name of the CSV file.

    Returns:
        str: Either "AWS" or "Azure" depending on the header of the CSV file.
    """
    with open(filename, "r") as file:
        reader = csv.reader(file)
        header = next(reader)

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
            return aws_parser.main

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
            return azure_parser.main

        # If neither set of required columns are present, return None
        return None


@click.command()
@click.argument("billing_csv", type=click.Path(exists=True))
def main(billing_csv: str = None) -> None:
    """
    The main function of the script. Parses the billing CSV file and writes the results to an Excel file.

    Args:
        billing_csv (str): The path to the billing CSV file.
    """
    if parser := get_csv_parser(billing_csv):
        parser(billing_csv)
    else:
        print("Invalid CSV format")


if __name__ == "__main__":
    main()
