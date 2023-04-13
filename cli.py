import click

from .get_parser import get_csv_parser


@click.command()
@click.argument("billing_csv", type=click.Path(exists=True))
def cli(billing_csv: str = None) -> None:
    """
    The main function of the script. Parses the billing CSV file and writes the results to an Excel file.

    Args:
        billing_csv (str): The path to the billing CSV file.
    """
    if parser := get_csv_parser(billing_csv)[1]:
        parser(billing_csv)
    else:
        print("Invalid CSV format")


if __name__ == "__main__":
    cli()
