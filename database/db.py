import mysql.connector
import datetime
import logging
log = logging.getLogger()
import os

def convert_to_date_string(data):
    if isinstance(data, datetime.date):  # Check if it's a datetime.date object
        return data.strftime('%Y-%m-%d')
    else:
        return data  #


class Connection:
    def __init__(self, user, password, host):  # Constructor to initialize connection
        self.cnx = mysql.connector.connect(
            user=user,
            password=password,
            host=host,
            database=os.environ['DB_NAME']
        )

    def get_recent_main_data(self, table='main'):
        results = {}
        cursor = self.cnx.cursor()  # Get cursor from existing connection
        query = f"SELECT product.name, {table}.* FROM {table} " \
                f"inner join (SELECT product_id, MAX(update_date) as max_update_date from {table} GROUP BY product_id)" \
                f"AS subquery on {table}.product_id = subquery.product_id AND {table}.update_date = subquery.max_update_date " \
                f"inner join product on product.id = {table}.product_id"
        cursor.execute(query)
        data = cursor.fetchall()
        for item in data:
            if str(item[2] not in results):
                item_id = str(item[2])
                bonus_start_date = "" if item[12] is None else item[12]
                bonus_end_date = "" if item[13] is None else item[13]
                update_date = "" if item[14] is None else item[14]
                bonus_type = None if item[11] == "" else item[11]
                result = {
                    "size": item[3],
                    "unit_type_id": item[4],
                    "unit_size": item[5],
                    "base_price": item[6],
                    "unit_price": item[7],
                    "bonus_price": item[8],
                    "bonus_unit_price": item[9],
                    "is_bonus": item[10],
                    "bonus_type": bonus_type,
                    "bonus_start_date": convert_to_date_string(bonus_start_date),
                    "bonus_end_date": convert_to_date_string(bonus_end_date),
                    "update_date": convert_to_date_string(update_date)
                }
                results[item_id] = result

        return results

    def insert(self, table, json_data_list, batch_size=1000):
        log.info(f"Trying to insert records into table {table}")
        cursor = self.cnx.cursor()  # Get cursor from existing connection

        try:

            # Construct the SQL query for bulk insert
            columns = json_data_list[0].keys()  # Assuming all objects have the same structure
            query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))})"

            # Process data in batches
            for i in range(0, len(json_data_list), batch_size):
                batch_data = json_data_list[i:i + batch_size]

                # Convert batch data to tuples for bulk insertion
                data_tuples = [tuple(data[col] for col in columns) for data in batch_data]

                # Execute the bulk insert for the batch
                cursor.executemany(query, data_tuples)

                # Commit the changes for the batch
                self.cnx.commit()

                log.info(f"Successfully inserted {len(batch_data)} rows (batch {i // batch_size + 1}) into the table {table}.")

        except mysql.connector.Error as err:
            log.error(f"Error: {err}")
            self.cnx.rollback()  # Rollback changes in case of an error

    def close(self):  # Method to close connection when done
        self.cnx.close()
