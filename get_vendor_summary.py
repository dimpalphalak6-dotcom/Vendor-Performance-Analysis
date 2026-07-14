import sqlite3
import pandas as pd
import logging
def ingest_db(df, table_name, conn):
    df.to_sql(table_name, conn, if_exists='replace', index=False)


logging.basicConfig(
    filename="logs/get_vendor_summary.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a"
)

def create_vendor_summary(conn):
    """This function merges different tables to get the overall vendor summary and adds new columns in the resultant DataFrame."""
    query = """
        WITH FreightSummary AS (
            SELECT
                VendorNumber,
                SUM(Freight) AS FreightCost
            FROM vendor_invoice
            GROUP BY VendorNumber
        ),
        PurchaseSummary AS (
            SELECT
                p.VendorNumber,
                p.VendorName,
                p.Brand,
                p.Description,
                p.PurchasePrice,
                pp.Price AS ActualPrice,
                pp.Volume,
                SUM(p.Quantity) AS TotalPurchaseQuantity,
                SUM(p.Dollars) AS TotalPurchaseDollars
            FROM purchases p
            JOIN purchase_prices pp ON p.Brand = pp.Brand
            WHERE p.PurchasePrice > 0
            GROUP BY p.VendorNumber, p.VendorName, p.Brand, p.Description, p.PurchasePrice, pp.Price, pp.Volume
        ),
        SalesSummary AS (
            SELECT
                VendorNo AS VendorNumber,
                Brand,
                SUM(SalesQuantity) AS TotalSalesQuantity,
                SUM(SalesDollars) AS TotalSalesDollars,
                SUM(SalesPrice) AS TotalSalesPrice,
                SUM(ExciseTax) AS TotalExciseTax
            FROM sales
            GROUP BY VendorNo, Brand
        )
        SELECT
            ps.VendorNumber,
            ps.VendorName,
            ps.Brand,
            ps.Description,
            ps.PurchasePrice,
            ps.ActualPrice,
            ps.Volume,
            ps.TotalPurchaseQuantity,
            ps.TotalPurchaseDollars,
            ss.TotalSalesQuantity,
            ss.TotalSalesDollars,
            ss.TotalSalesPrice,
            ss.TotalExciseTax,
            fs.FreightCost
        FROM PurchaseSummary ps
        LEFT JOIN SalesSummary ss ON ps.VendorNumber = ss.VendorNumber AND ps.Brand = ss.Brand
        LEFT JOIN FreightSummary fs ON ps.VendorNumber = fs.VendorNumber
        ORDER BY ps.TotalPurchaseDollars DESC
    """
    return pd.read_sql_query(query, conn)

def clean_data(df):
    """This function will clean the data and create derived metrics."""

    # Convert to correct data types
    df['Volume'] = df['Volume'].astype(float)

    # Fill missing values
    df.fillna(0, inplace=True)

    # Strip white spaces
    df['VendorName'] = df['VendorName'].str.strip()
    df['Description'] = df['Description'].str.strip()

    # Derived metrics
    df['GrossProfit'] = df['TotalSalesDollars'] - df['TotalPurchaseDollars']
    df['ProfitMargin'] = ((df['GrossProfit'] / df['TotalSalesDollars']) * 100).round(2)
    df['StockTurnover'] = df['TotalSalesQuantity'] / df['TotalPurchaseQuantity']
    df['SalesToPurchaseRatio'] = df['TotalSalesDollars'] / df['TotalPurchaseDollars']

    return df

if __name__ == '__main__':
    # Creating database connection
    conn = sqlite3.connect('inventory.db')

    logging.info('Creating Vendor Summary Table...')
    summary_df = create_vendor_summary(conn)

    logging.info('Cleaning Data...')
    clean_df = clean_data(summary_df)

    logging.info('Preview Clean Data:')
    logging.info(clean_df.head())

    logging.info('Ingesting data into database...')
    ingest_db(clean_df, 'vendor_sales_summary', conn)

    logging.info('Completed')
