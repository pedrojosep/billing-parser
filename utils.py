import pandas as pd


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
