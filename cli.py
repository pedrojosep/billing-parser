import click
import pandas as pd

from rich.console import Console

from parsers import get_csv_parser


def write_excel(df: pd.DataFrame, total_df: pd.DataFrame) -> None:
    """
    Write a pandas DataFrame to an Excel file.

    Args:
        df (pd.DataFrame): The original DataFrame.
        total_df (pd.DataFrame): The aggregated DataFrame.
    """
    print("Saving results into output.xlsx")
    writer = pd.ExcelWriter("output.xlsx", engine="xlsxwriter")
    total_df.to_excel(writer, sheet_name="Total")
    df.to_excel(writer, sheet_name="Original")
    writer.close()


@click.command()
@click.argument("billing_csv", type=click.Path(exists=True))
@click.option(
    "--use-cache/--no-cache",
    default=True,
    help="Enable or disable use of cache (default: enabled)",
)
def cli(
    billing_csv: str = None,
    use_cache: bool = True,
) -> None:
    """
    The main function of the script. Parses the billing CSV file and writes the results to an Excel file.

    Args:
        billing_csv (str): The path to the billing CSV file.
        use_cache (bool): Optional boolean flag to enable or disable use of cache (default: enabled).
    """
    parser_description, parser = get_csv_parser(billing_csv)
    if parser:
        print(parser_description)
        df, total_df = parser(billing_csv, use_cache=use_cache)

        # Use Rich to display the dataframe
        console = Console()
        console.print(total_df, justify="left")

        write_excel(df, total_df)

    else:
        print("Invalid CSV format")


if __name__ == "__main__":
    cli()
