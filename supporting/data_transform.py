import supporting.general as sg
import re
import logging

formatter = logging.Formatter('[%(levelname)s] %(message)s')
log = logging.getLogger()
log.setLevel("INFO")


def get_bonus_price(size, bonus, og_price, unit_size, ignore_bonus_values_exact, ignore_bonus_values_contains):
    try:
        # ignore_bonus_values = ['bonus', 'online met gratis glas', 'online met gratis koeltas', 'gratis koeltas bij 2 6-packs']
        bonus = bonus.lower()
        absolute_price = 9999999999
        absolute_discount = 0
        factor = 1
        unknown_bonus = ""
        send_warning = True

        if bonus in ignore_bonus_values_exact:
            return [round(float(str(og_price).replace(',', '.')), 2), round(float(str(og_price).replace(',', '.'))/float(str(size).replace(',', '.'))*float(str(unit_size).replace(',', '.')), 2), unknown_bonus]

        for item in ignore_bonus_values_contains:
            if item in bonus:
                return [round(float(str(og_price).replace(',', '.')), 2), round(float(str(og_price).replace(',', '.'))/float(str(size).replace(',', '.'))*float(str(unit_size).replace(',', '.')), 2), unknown_bonus]

        if "volume voordeel" in bonus:
            factor = (100-float(str(bonus[:bonus.find('%')]).replace(',', '.')))/100
            send_warning = False

        elif 'stapelen voor' in bonus and 'per' not in bonus:
            factor = 1/(float(str(bonus.split(' ')[0])))
            absolute_price = round(factor * (float(str(bonus.split(' ')[3]).replace(',', '.'))), 2)
            send_warning = False
        elif 'stuks voor' in bonus and 'per' not in bonus:
            factor = 1/(float(str(bonus.split(' ')[0])))
            absolute_price = round(factor * (float(str(bonus.split(' ')[3]).replace(',', '.'))), 2)
            send_warning = False
        elif 'gram voor' in bonus and 'per' not in bonus:
            absolute_price = float(str(bonus.split(' ')[3]).replace(',', '.'))
            send_warning = False

        elif "korting" in bonus:

            if "stapelen tot" in bonus:
                factor = (100-float(str(bonus.split(' ')[2][:bonus.split(' ')[2].find('%')]).replace(',', '.')))/100
                send_warning = False
            elif "online" in bonus:
                factor = (100-float(str(bonus.split(' ')[1][:bonus.split(' ')[1].find('%')]).replace(',', '.')))/100
                send_warning = False
            elif '%' in bonus:
                factor = (100-float(str(bonus[:bonus.find('%')]).replace(',', '.')))/100
                send_warning = False
            elif ' euro' in bonus:
                absolute_discount = float(str(bonus[:bonus.find(' euro')]).replace(',', '.'))
                send_warning = False
            else:
                absolute_discount = float(str(bonus[0]).replace(',', '.'))
                send_warning = False
        elif "gratis" in bonus:
            if len(bonus.split(" ")) == 2:
                number = float(str(bonus.split(" ")[0][0]).replace(',', '.'))
                factor = 1-(1/number)
                send_warning = False
            else:
                number1 = float(str(bonus.split(" ")[0]).replace(',', '.'))
                number2 = float(str(bonus.split(" ")[2]).replace(',', '.'))
                factor = number1 / (number1 + number2)
                send_warning = False
        elif len(bonus.split(" ")) == 2:
            if bonus.split(" ")[0] == 'voor':
                absolute_price = bonus.split(" ")[1]
                send_warning = False
        elif len(bonus.split(" ")) == 3:
            if bonus.split(" ")[1] == 'voor':
                absolute_price = float(str(bonus.split(" ")[2]).replace(',', '.')) / float(str(bonus.split(" ")[0]).replace(',', '.'))
                send_warning = False
            elif bonus == '2e halve prijs':
                factor = 0.75
                send_warning = False

            elif bonus.split(" ")[0] == "stapelen" and bonus.split(" ")[1] == "tot":
                factor = (100-float(str(bonus.split(' ')[2][:bonus.split(' ')[2].find('%')]).replace(',', '.')))/100
                send_warning = False

        elif len(bonus.split(" ")) == 5:
            if bonus.split(" ")[0] == 'per' and bonus.split(" ")[2] == 'gram':
                absolute_price = float(str(size).replace(',', '.')) / float(str(bonus.split(" ")[1]).replace(',', '.')) * float(str(bonus.split(" ")[4]).replace(',', '.'))
                send_warning = False

        new_price = (og_price - absolute_discount) * factor
        if absolute_price != 9999999999:
            new_price = absolute_price

        if new_price == og_price and send_warning:
            unknown_bonus = bonus
            log.info(f'Bonustype {bonus} not in default')

        new_price = str(new_price).replace(',', '.')
        return [round(float(str(new_price).replace(',', '.')), 2), round(float(str(new_price).replace(',', '.'))/float(str(size).replace(',', '.'))*float(str(unit_size).replace(',', '.')), 2), unknown_bonus]

    except Exception as e:
        log.warning(f'Bonus {bonus} could not be determined')
        log.warning(e)
        return [round(float(str(og_price).replace(',', '.')), 2), round(float(str(og_price).replace(',', '.'))/float(str(size).replace(',', '.'))*float(str(unit_size).replace(',', '.')), 2), bonus]


def search_alternative_unit(product_id, size, unit_type, unit_size, unit_price, connector, base_price):
    if unit_type == "persoon" or unit_type == "" or unit_type == "artikel" or unit_type == "blik" or unit_type == "bosje"\
             or unit_type == "bundel" or unit_type == "doos" or unit_type == "pack" or unit_type == "paar"\
            or unit_type == "pakket" or unit_type == "plakjes":
        product_info = connector.get_product_details(product=product_id)
        try:
            new_size = product_info['tradeItem']['measurements']['netContent'][0]['value']
            new_unit_type = product_info['tradeItem']['measurements']['netContent'][0]['measurementUnitCode']['value']
            if new_unit_type.strip().lower() in ['g', 'gram', 'gr', 'ml']:
                new_unit_size = 1000

            elif new_unit_type.strip().lower() in ['l', 'lt', 'liter', 'kg', 'blik', 'kilogram', 'kilo', 'st', 'pakket', 'stuks', 'wasbeurten', 'personen', 'tros',
                                                   'doos', 'los per kilo', 'paar', 'dozen', 'meter', 'plakjes',  'rollen', 'stuk', 'tabletten', 'sachets']:
                new_unit_size = 1

            elif new_unit_type.strip().lower() in ['cl']:
                new_unit_size = 100
            else:
                new_unit_size = unit_size

            new_unit_price = round(base_price / float(str(new_size).replace(',', '.')) * float(str(new_unit_size).replace(',', '.')), 2)
            return [new_size, new_unit_type, new_unit_size, new_unit_price]

        except ValueError:
            return [size, unit_type, unit_size, unit_price]

        except ZeroDivisionError:
            # quit()
            return [size, unit_type, unit_size, unit_price]

        except TypeError:
            # quit()
            return [size, unit_type, unit_size, unit_price]

        except KeyError:
            # quit()
            return [size, unit_type, unit_size, unit_price]
    else:
        return [size, unit_type, unit_size, unit_price]


def simplify_unit_type(value):

    if value.lower() in ['g', 'gr', 'gram']:
        return 'g'
    elif value.lower() in ['kg', 'kilo', 'kilogram']:
        return 'kg'
    elif value.lower() in ['l', 'lt', 'liter']:
        return 'l'
    elif value.lower() in ['doos', 'dozen']:
        return 'doos'
    elif value.lower() in ['st', 'stuk', 'per stuk', 'stuks']:
        return 'stuk'
    elif value.lower() in ['rollen', 'rol']:
        return 'rol'
    elif value.lower() in ['wasbeurten']:
        return 'wasbeurt'
    elif value.lower() in ['personen']:
        return 'persoon'
    else:
        return value.lower()


def size_definition(size):
    return_size = size
    return_unit_type = size
    return_unit_size = ''
    define_unit_size = True
    if 'pers' in size and 'personen' not in size:
        return_unit_type = 'personen'
        return_unit_size = 1
        return_size = size.split(' ')[0]
        if sg.is_float(return_size):
            return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]
        elif '-' in return_size:
            number1 = float(str(return_size.split('-')[0]).replace(',', '.'))
            number2 = float(str(return_size.split('-')[1]).replace(',', '.'))
            return_size = (number1 + number2) / 2
            return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]

    elif len(size.split(' ')) == 2:
        return_size = size.split(' ')[0]
        return_unit_type = size.split(' ')[1]
        if return_size.lower() == 'pet' or return_size.lower() == 'per':
            return_size = 1
            return_unit_type = size.split(' ')[1]
            return_unit_size = 1
            return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]
        if '-' in size.split(' ')[0]:
            number1 = float(size.split('-')[0].replace(',', '.'))
            number2 = float(size.split('-')[1].split(' ')[0].replace(',', '.'))
            return_size = (number1 + number2) / 2
            return_unit_type = size.split(' ')[1]
            return_unit_size = 1
            return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]
        if 'x' in size.split(' ')[0]:
            number1 = float(size.split(' ')[0].split('x')[0].replace(',', '.'))
            number2 = float(size.split(' ')[0].split('x')[1].replace(',', '.'))
            return_size = number1 * number2
            return_unit_type = size.split(' ')[1]

    elif len(size.split(' ')) == 5:
        number1 = float(size.split(' ')[0])
        number2 = float(size.split(' ')[3])
        return_size = number1 * number2
        return_unit_type = 'm²'
        return_unit_size = 1
        if size.split(' ')[1] == 'cm':
            return_size = 100
        if size.split(' ')[4] == 'cm':
            return_size = 100
        return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]

    elif len(size.split(' ')) == 4:
        if size.split(' ')[1] == 'x':
            return_size = float(size.split(' ')[0].replace(',', '.')) * float(size.split(' ')[2].replace(',', '.'))
            return_unit_type = size.split(' ')[3]

        elif size.split(' ')[0] == 'los':
            return_size = size.split(' ')[2]
            return_unit_type = size.split(' ')[3]

        elif ',' in size.split(' ')[1]:
            return_size = size.split(' ')[0]
            return_unit_type = size.split(' ')[1][:-1]

        elif size.split(' ')[1] == '+':
            return_size = float(size.split(' ')[0]) + float(size.split(' ')[0])
            return_unit_type = size.split(' ')[3]

    elif 'ca.' in size:
        return_size = size.split(' ')[1]
        return_unit_type = size.split(' ')[2]

    elif len(size.split('-')) == 2:
        return_size = size.split('-')[0]
        return_unit_type = size.split('-')[1]
        return_unit_size = 1
        return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]

    elif len(size.split(' ')) == 3:
        if size.split(' ')[1] == 'per' and size.split(' ')[0] == 'los':
            return_size = 1
            return_unit_type = size.split(' ')[2]
        elif size.split(' ')[0] == 'per' or size.split(' ')[0] == 'los':
            return_size = size.split(' ')[1]
            return_unit_type = size.split(' ')[2]
        elif 'ca' in size.split(' ')[0]:
            return_size = size.split(' ')[1]
            return_unit_type = size.split(' ')[2]
        elif 'x' in size.split(' ')[0]:
            number1 = float(size.split(' ')[0][:size.split(' ')[0].find('x')].replace(',', '.'))
            number2 = float(size.split(' ')[1].replace(',', '.'))
            return_size = number1 * number2
            return_unit_type = size.split(' ')[2]
        elif size.split(' ')[1] == 'x':
            number1 = size.split(' ')[0]
            number2 = re.match(r"(\d+(?:\.\d+)?)(.*)", size.split(' ')[2].replace(',', '.')).group(1)
            return_size = float(number1) * float(number2)
            return_unit_type = re.match(r"(\d+(?:\.\d+)?)(.*)", size.split(' ')[2].replace(',', '.')).group(2)
    elif size.lower() in ['pakket', 'doos', 'tros']:
        return_size = 1
        return_unit_type = size

    elif sg.is_integer(size):
        return_size = size
        return_unit_type = 'gr'

    elif ' ' not in size:
        if 'x' in size:
            number1 = float(size[:size.find('x')].replace(',', '.'))
            number2 = float(re.match(r"(\d+(?:\.\d+)?)(.*)", size.split('x')[1].replace(',', '.')).group(1))
            return_size = number1 * number2
            return_unit_type = re.match(r"(\d+(?:\.\d+)?)(.*)", size.split('x')[1].replace(',', '.')).group(2)
        elif re.match(r"(\d+(?:\.\d+)?)(.*)", size):
            return_size = float(re.match(r"(\d+(?:\.\d+)?)(.*)", size.replace(',', '.')).group(1))
            return_unit_type = re.match(r"(\d+(?:\.\d+)?)(.*)", size.replace(',', '.')).group(2)

    else:
        return_size = size
        return_unit_type = size
        return_unit_size = ''
        return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]

    if define_unit_size:
        if return_unit_type.strip().lower() in ['g', 'gram', 'gr', 'ml']:
            return_unit_size = 1000

        elif return_unit_type.strip().lower() in ['l', 'lt', 'liter', 'kg', 'blik', 'kilogram', 'kilo', 'st', 'pakket', 'stuks', 'wasbeurten', 'personen', 'tros',
                                                  'doos', 'los per kilo', 'paar', 'dozen', 'meter', 'plakjes',  'rollen', 'stuk', 'tabletten', 'sachets']:
            return_unit_size = 1
        elif return_unit_type.strip().lower() in ['cl']:
            return_unit_size = 100
    # if 'los per' in size:
    #     print(size)
    #     print([return_size, return_unit_type, return_unit_size])

    return [str(return_size).replace(',', '.'), return_unit_type, return_unit_size]
