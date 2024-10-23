from database.db import Connection
import supporting.data_transform as dt
import supporting.general as sg
from supporting.ah import AHConnector
import json
import math
from datetime import date
import boto3
import logging
import requests


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

id = 569985
connector = AHConnector()

result = connector.get_product_details(product=id)
print(json.dumps(result))

# product_details = ah.get_product_details(product=id)
# print(product_details)
