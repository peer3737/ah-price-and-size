from database.db import Connection
import supporting.data_transform as dt
import supporting.general as sg
from supporting import aws
from supporting.ah import AHConnector
import json
import math
from datetime import date
import boto3
import logging
import os


formatter = logging.Formatter('[%(levelname)s] %(message)s')
log = logging.getLogger()
log.setLevel("INFO")
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
for handler in log.handlers:
    log.removeHandler(handler)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
log.addHandler(handler)


def write_to_db(products, price_and_size, current_data, db_user, db_password, db_host):
    db = Connection(user=db_user, password=db_password, host=db_host)  # Establish the connection
    products_to_db = []
    prices_and_sizes_to_db = []
    for product in json.loads(products):
        if str(product["id"]) not in current_data:
            products_to_db.append(product)

    for product in json.loads(price_and_size):
        prices_and_sizes_to_db.append(product)

    if len(products_to_db) > 0:
        log.info("Write new products to db")
        log.info(products_to_db)
        db.insert(table='product', json_data_list=products_to_db)
    if len(prices_and_sizes_to_db) > 0:
        log.info("Write new prices and sizes to db")
        log.info(prices_and_sizes_to_db)
        db.insert(table='main', json_data_list=prices_and_sizes_to_db)

    db.close()


def lambda_handler(event, context):
    database_id = os.environ['DATABASE_ID']
    database_settings = aws.dynamodb_query(table='database_settings', id=database_id)
    db_host = database_settings[0]['host'][0]
    db_user = database_settings[0]['user']
    db_password = database_settings[0]['password']
    lambda_client = boto3.client('lambda')
    s3 = boto3.client('s3')
    bucket_name = os.environ['MAIN_BUCKET']

    settings_file = s3.get_object(Bucket=bucket_name, Key=os.environ['SETTINGS_FILE'])
    settings_file_content = json.loads(settings_file['Body'].read().decode('utf-8'))
    ignore_bonus_values_exact = settings_file_content["ignore_bonus_values_exact"]
    ignore_bonus_values_contains = settings_file_content["ignore_bonus_values_contains"]
    # sys.exit(1)
    # Write JSON data to a file-like object

    try:
        unknown_bonus_values = []
        today = date.today().strftime('%Y-%m-%d')
        log.info("Setup API connection with AH API")
        connector = AHConnector()
        db = Connection(user=db_user, password=db_password, host=db_host)  # Establish the connection
        current_data = db.get_recent_main_data()
        db.close()
        page_size = 1000
        max_page = math.floor(3000 / page_size)
        log.info("Retrieve categories")
        categories = connector.get_categories()
        category_list = []
        for cat in categories:
            cat_id = cat['id']
            cat_name = cat['name']
            category_list.append({
                "id": cat_id,
                "name": cat_name
            })

        #
        # category_list = ['20128', '18519', '1301', '1555', '18521', '1043', '6406', '1057', '2457', '5881', '1355', '1688',
        #               '1165', '1662', '11717', '1730', '20130', '6401', '6402', '6405', '1045', '1796', '20129', '6409']
        # category_list = [
        #     {
        #         "id": "1045",
        #         "name": "Drogisterij"
        #     }
        # ]

        id_list = []
        bonus_types = []
        output = ""
        json_output = []
        product_output = []

        # categories = ['20128']

    except Exception as e:
        log.error(str(e))
        log.info('Mailing error')
        payload = {
            "to": os.environ['MAIL_CONTACT'],
            "from": os.environ['MAIL_SENDER'],
            "subject": "Foutmelding bij verwerken AH",
            "content": str(e)
        }

        lambda_client.invoke(
            FunctionName='sendMail',  # Replace with the name of your sendMail function
            InvocationType='Event',  # Use 'RequestResponse' for synchronous invocation
            Payload=json.dumps(payload)
        )
        return {
            'statusCode': 500,
            'body': f'Error uploading JSON data: {str(e)}'
        }

    for cat in category_list:
        log.info(f"{cat['name']} - {cat['id']} is being processed")
        page = -1
        results = 1000
        items = []
        counter = 0
        while results == page_size and page < max_page-1:
            page += 1
            all_products = connector.search_products(page=page, size=page_size, category=cat["id"])
            for item in all_products["products"]:
                items.append(item)
        log.info(f"{len(items)} found")
        for item in items:
            counter += 1
            try:
                if 'productCard' in item:
                    item_id = item['productCard']['webshopId']
                    if item_id in id_list:
                        continue
                    else:
                        id_list.append(item_id)
                        name = item['productCard']['title']
                        if 'salesUnitSize' not in item:
                            size = '1'
                            unit_type = 'per stuk'
                            unit_size = 1
                        else:
                            sizes = dt.size_definition(item['productCard']['salesUnitSize'].strip())
                            size = sizes[0]
                            if sg.is_float(size):
                                size = round(float(sizes[0]), 2)
                            unit_type = sizes[1]
                            unit_size = sizes[2]

                        if 'priceBeforeBonus' in item['productCard']:
                            before_bonus_price = item['productCard']['priceBeforeBonus']
                        else:
                            before_bonus_price = item['productCard']['currentPrice']

                        base_price = before_bonus_price

                        try:
                            unit_price = round(base_price / float(str(size).replace(',', '.')) * float(unit_size), 2)

                        except ValueError:
                            unit_price = "-"

                        except ZeroDivisionError:
                            unit_price = "-"

                        except TypeError:
                            unit_price = "-"

                        bonus_price = before_bonus_price
                        bonus_unit_price = before_bonus_price

                        if 'bonusMechanism' in item['productCard']:
                            bonus_type = item['productCard']['bonusMechanism']
                            if bonus_type not in bonus_types:
                                bonus_types.append(bonus_type)
                            is_bonus = True

                        else:
                            bonus_type = ""
                            is_bonus = False
                            if 'promotionType' in item['productCard']:
                                if item['productCard']['promotionType'].lower() == 'ahonline':
                                    is_bonus = True
                                    bonus_type = 'ONLINE PAKKETKORTING'
                                    bonus_types.append(bonus_type)

                        if 'bonusStartDate' in item['productCard']:
                            bonus_start_date = item['productCard']['bonusStartDate']

                        else:
                            bonus_start_date = None
                        if 'bonusEndDate' in item['productCard']:
                            bonus_end_date = item['productCard']['bonusEndDate']
                        else:
                            bonus_end_date = None
                        if bonus_type == 'DEFAULT 2':
                            is_bonus = False
                            bonus_type = ""

                    if 'priceBeforeBonus' in item and 'currentPrice' in item and is_bonus:
                        bonus_function = False
                        bonus_price = item['productCard']['currentPrice']
                    else:
                        bonus_function = True

                else:
                    item_id = item['webshopId']
                    if item_id in id_list:
                        continue
                    else:
                        id_list.append(item_id)
                        name = item['title']

                        if 'salesUnitSize' not in item:
                            size = '1'
                            unit_type = 'per stuk'
                            unit_size = 1
                        else:
                            sizes = dt.size_definition(item['salesUnitSize'].strip())
                            size = sizes[0]
                            if sg.is_float(size):
                                size = round(float(sizes[0]), 2)
                            unit_type = sizes[1]
                            unit_size = sizes[2]

                        if 'priceBeforeBonus' not in item and 'currentPrice' not in item:
                            continue
                        else:
                            if 'priceBeforeBonus' in item:
                                before_bonus_price = item['priceBeforeBonus']
                            else:
                                before_bonus_price = item['currentPrice']

                            base_price = before_bonus_price
                            try:
                                unit_price = round(base_price / float(str(size).replace(',', '.')) * float(unit_size),
                                                   2)
                            except ValueError:
                                unit_price = "-"

                            except ZeroDivisionError:
                                unit_price = "-"

                            except TypeError:
                                unit_price = "-"

                            bonus_price = before_bonus_price
                            bonus_unit_price = before_bonus_price

                            if 'bonusMechanism' in item:
                                bonus_type = item['bonusMechanism']
                                if bonus_type not in bonus_types:
                                    bonus_types.append(bonus_type)
                                is_bonus = True
                            else:
                                bonus_type = ""
                                is_bonus = False
                                if 'promotionType' in item:
                                    if item['promotionType'].lower() == 'ahonline':
                                        is_bonus = True
                                        bonus_type = 'ONLINE PAKKETKORTING'
                                        bonus_types.append(bonus_type)
                            if 'bonusStartDate' in item:
                                bonus_start_date = item['bonusStartDate']
                            else:
                                bonus_start_date = None
                            if 'bonusEndDate' in item:
                                bonus_end_date = item['bonusEndDate']
                            else:
                                bonus_end_date = None
                            if bonus_type == 'DEFAULT 2':
                                is_bonus = False
                                bonus_type = ""

                    if 'priceBeforeBonus' in item and 'currentPrice' in item and is_bonus:
                        bonus_function = False
                        bonus_price = item['currentPrice']

                    else:
                        bonus_function = True

                unit_type = dt.simplify_unit_type(unit_type)

                # if unit_type == 'g':
                #     unit_type = 'kg'
                #     unit_size = 1
                #     unit_price *= 1000

                new_sizing = dt.search_alternative_unit(item_id, size, unit_type, unit_size, unit_price, connector, base_price)
                size, unit_type, unit_size, unit_price = new_sizing[0], new_sizing[1], new_sizing[2], new_sizing[3]

                if is_bonus:
                    if bonus_function:
                        bonus_prices = dt.get_bonus_price(item_id, size, bonus_type, base_price, unit_size, ignore_bonus_values_exact, ignore_bonus_values_contains)
                        bonus_price, bonus_unit_price, unknown_bonus = bonus_prices[0], bonus_prices[1], bonus_prices[2]
                        if unknown_bonus != "":
                            if unknown_bonus not in unknown_bonus_values:
                                unknown_bonus_values.append(unknown_bonus)
                    else:
                        bonus_unit_price = round(float(bonus_price) / float(base_price) * float(unit_price), 2)

                product = {
                    "id": item_id,
                    "name": name
                }
                # bonus_check = False
                # if bonus_start_date is not None and bonus_end_date is not None:
                #     if bonus_start_date <= today or bonus_end_date > today:
                #         bonus_check = True
                #  if bonus_start_date is None and bonus_end_date is None:

                if str(item_id) in current_data:
                    if float(current_data[str(item_id)]["size"]) != float(size) or current_data[str(item_id)]["unit_type_id"] != unit_type or float(current_data[str(item_id)]["unit_size"]) != float(unit_size) or float(current_data[str(item_id)]["base_price"]) != float(base_price) or float(current_data[str(item_id)]["unit_price"]) != float(unit_price):
                        insert_values = True
                    elif float(current_data[str(item_id)]["bonus_price"]) != float(bonus_price) or float(current_data[str(item_id)]["bonus_unit_price"]) != float(bonus_unit_price):
                        insert_values = True
                    elif current_data[str(item_id)]["is_bonus"] == 0 and is_bonus:
                        insert_values = True
                    elif current_data[str(item_id)]["is_bonus"] == 1 and not is_bonus:
                        insert_values = True
                    elif current_data[str(item_id)]["bonus_type"] is None:
                        current_data[str(item_id)]["bonus_type"] = ""
                        if current_data[str(item_id)]["bonus_type"] != bonus_type:
                            insert_values = True
                        else:
                            insert_values = False
                        # if bonus_check:
                        #     insert_values = True
                    else:
                        insert_values = False

                else:
                    product_output.append(product)
                    insert_values = True

                if insert_values:
                    json_output_item = {
                        "product_id": item_id,
                        "size": size,
                        "unit_type_id": unit_type,
                        "unit_size": unit_size,
                        "base_price": base_price,
                        "unit_price": unit_price,
                        "bonus_price": bonus_price,
                        "bonus_unit_price": bonus_unit_price,
                        "is_bonus": is_bonus,
                        "bonus_type": bonus_type,
                        "bonus_start_date": bonus_start_date,
                        "bonus_end_date": bonus_end_date,
                        "update_date": today
                    }

                    json_output.append(json_output_item)

                    output += f"{item_id}\t{name.strip()}\t{float(size)}\t{unit_type}\t{unit_size}\t{base_price}\t{unit_price}" \
                              f"\t{bonus_price}\t{bonus_unit_price}\t{is_bonus}\t{bonus_type}\t{bonus_start_date}\t{bonus_end_date}\n"

            except Exception as e:
                log.error('An error occurred')
                log.error(json.dumps(item))
                log.error(e)

    if len(unknown_bonus_values) > 0:
        log.info('Mailing unknown bonus values')
        content = "De volgende bonuswaarden konden niet worden verwerkt:\n" + "\n".join([f"-{bonus}" for bonus in unknown_bonus_values])
        payload = {
            "to": os.environ['MAIL_CONTACT'],
            "subject": "Ongeldige bonuswaarden",
            "content": content
        }
        lambda_client.invoke(
            FunctionName='sendMail',  # Replace with the name of your sendMail function
            InvocationType='Event',  # Use 'RequestResponse' for synchronous invocation
            Payload=json.dumps(payload)
        )
    log.info('Create json files')

    try:

        today = date.today()
        folder_name = today.strftime('%Y-%m-%d') + '/'
        # Write JSON data to a file-like object
        price_size_file = json.dumps(json_output).encode('utf-8')
        product_file = json.dumps(product_output).encode('utf-8')
        current_data_file = json.dumps(current_data).encode('utf-8')

        s3.put_object(
            Bucket=bucket_name,
            Key=folder_name + 'price_and_size.json',
            Body=price_size_file
        )
        s3.put_object(
            Bucket=bucket_name,
            Key=folder_name + 'products.json',
            Body=product_file
        )
        s3.put_object(
            Bucket=bucket_name,
            Key=folder_name + 'current_data.json',
            Body=current_data_file
        )
        log.info('JSON files successfully created and uploaded to S3')
        write_to_db(product_file, price_size_file, current_data, db_user, db_password, db_host)

        return {
            'statusCode': 200,
            'body': 'files created successfully'
        }

    except Exception as e:
        log.error('JSON files not created and uploaded to S3')
        log.error(e)
        log.info('Mailing error')
        payload = {
            "to": os.environ['MAIL_CONTACT'],
            "subject": "JSON files not created and uploaded to S3",
            "content": str(e)
        }

        lambda_client.invoke(
            FunctionName='sendMail',  # Replace with the name of your sendMail function
            InvocationType='Event',  # Use 'RequestResponse' for synchronous invocation
            Payload=json.dumps(payload)
        )
        return {
            'statusCode': 500,
            'body': f'Error uploading JSON data: {str(e)}'
        }


lambda_handler(None, None)
