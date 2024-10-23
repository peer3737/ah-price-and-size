from datetime import date
from supporting import aws_client as aws
from database.db import Connection
import json

def read_files(day, s3):
    folder_name = day.strftime('%Y-%m-%d')
    bucket_name = 'ah-grocery'
    object_key_1 = f'{folder_name}/products.json'
    object_key_2 = f'{folder_name}/price_and_size.json'
    response_prod = s3.get_object(Bucket=bucket_name, Key=object_key_1)
    response_p_and_s = s3.get_object(Bucket=bucket_name, Key=object_key_2)
    file_content_1 = response_prod['Body'].read().decode('utf-8')  # Assuming the object is text
    file_content_2 = response_p_and_s['Body'].read().decode('utf-8')  # Assuming the object is text
    return file_content_1, file_content_2


s3 = aws.client(mfa=False, profile_name='ah-read-data')
if s3 != False:
    day = date.today()
    result = read_files(day, s3)
    products = result[0]
    price_and_size = result[1]
    db = Connection()  # Establish the connection
    current_data = db.get_recent_main_data()
    db.close()

    products_to_db = []
    prices_and_sizes_to_db = []
    for product in json.loads(products):
        if str(product["id"]) not in current_data:
            products_to_db.append(product)

    for product in json.loads(price_and_size):
        if str(product["product_id"]) not in current_data:
            prices_and_sizes_to_db.append(product)

    print(products_to_db)
    print(prices_and_sizes_to_db)
    # db = Connection()  # Establish the connection
    # db.insert(table='product', json_data_list=products_to_db)
    # db.insert(table='main', json_data_list=prices_and_sizes_to_db)
    # db.close()


