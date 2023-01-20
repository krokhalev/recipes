import time
import aiohttp
import asyncio
import aiofiles
from bs4 import BeautifulSoup as bs
import os
import json
import motor.motor_asyncio
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig()
logger = logging.getLogger(__name__)
level = logging.getLevelName(os.getenv('LOGGING_LEVEL'))
logger.setLevel(level)

URL = "https://eda.ru"
HEADERS = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"}


def init_mongo_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    username = os.getenv('MONGO_INITDB_ROOT_USERNAME')
    password = os.getenv('MONGO_INITDB_ROOT_PASSWORD')
    host = os.getenv('MONGO_HOST')
    return motor.motor_asyncio.AsyncIOMotorClient(f"mongodb://{username}:{password}@{host}:27017/?authMechanism=DEFAULT")


async def save_recipes_info(collection: motor.motor_asyncio.core.AgnosticCollection, recipes_info: list) -> None:
    await collection.insert_many(recipes_info)


async def save_image(recipe_name: str, image_url: str, headers: dict) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=image_url, headers=headers) as response:
                async with aiofiles.open(f"recipes_data/{recipe_name}/" + "".join(image_url.split("/")[-3:]), 'wb') as image:
                    await image.write(await response.read())
    except Exception as ex:
        logger.error(f"save image error: {ex}")

    return f"recipes_data/{recipe_name}/" + "".join(image_url.split("/")[-3:])


async def save_recipe_page_info(recipe_page_info: dict) -> None:
    try:
        json_obj_recipe_page_info = json.dumps(recipe_page_info, ensure_ascii=False)
        async with aiofiles.open(f"recipes_data/{recipe_page_info['recipe_name']}/{recipe_page_info['recipe_name']}.json", 'w') as file:
            await file.write(json_obj_recipe_page_info)
    except Exception as ex:
        logger.error(f"save recipe page info error: {ex}")


async def get_recipes_info(url: str, recipes_urls: list, headers: dict) -> list:
    recipes_info = []
    for recipe_url in recipes_urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url=url + recipe_url, headers=headers) as response:
                    soup = bs(await response.text(), "lxml")

        except RuntimeError as ex:
            logger.debug(f"get recipe page info error: {ex}")

        recipe_name = soup.find("h1", class_="emotion-gl52ge").text.strip().replace('\xa0', ' ')

        recipe_page_info = {
            "recipe_name": recipe_name,
            "portions": soup.find("span", {'itemprop': 'recipeYield'}).getText(),
            "cooking_time": soup.find("div", class_="emotion-my9yfq").text.strip()
        }

        recipe_id = soup.find("link", {'rel': 'canonical'}).get("href").split("-")[-1]
        recipe_page_info["_id"] = recipe_id

        if not os.path.exists(f"recipes_data/{recipe_name}/"):
            os.mkdir(f"recipes_data/{recipe_name}/")

        raw_tags = soup.find("div", class_="emotion-fq1t0q").findAll("li", {'itemprop': 'itemListElement'})
        tags = []
        for tag in raw_tags[1:]:
            tags.append(tag.getText())
        recipe_page_info["tags"] = tags

        preview_image_path = "no_path"
        try:
            preview_image_url = soup.find("span", {'itemprop': 'resultPhoto'}).get("content")
            preview_image_path = await save_image(recipe_name, preview_image_url, headers)
        except AttributeError:
            logger.debug(f'recipe "{recipe_name}" does not have preview image')

        recipe_page_info["preview_image_path"] = preview_image_path

        try:
            recipe_page_info["description"] = soup.find("span", class_="emotion-1x1q7i2").text.strip().replace('\xa0', ' ')
        except AttributeError:
            logger.debug(f'recipe "{recipe_name}" does not have description')

        ingredients = {}
        ingredients_list = soup.findAll("span", {'itemprop': 'recipeIngredient'})
        ingredients_weight_list = soup.findAll("span", class_="emotion-15im4d2")

        for index, ingredient in enumerate(ingredients_list):
            ingredients[ingredient.getText()] = ingredients_weight_list[index].getText()
        recipe_page_info["ingredients"] = ingredients

        nutritious = {}
        try:
            nutritious["calories"] = soup.find("span", {'itemprop': 'calories'}).text.strip()
        except AttributeError:
            nutritious["calories"] = "0"
        try:
            nutritious["proteinContent"] = soup.find("span", {'itemprop': 'proteinContent'}).text.strip()
        except AttributeError:
            nutritious["proteinContent"] = "0"
        try:
            nutritious["fatContent"] = soup.find("span", {'itemprop': 'fatContent'}).text.strip()
        except AttributeError:
            nutritious["fatContent"] = "0"
        try:
            nutritious["carbohydrateContent"] = soup.find("span", {'itemprop': 'carbohydrateContent'}).text.strip()
        except AttributeError:
            nutritious["carbohydrateContent"] = "0"
        recipe_page_info["nutritious"] = nutritious

        steps = []
        pattern = soup.findAll("div", {'itemprop': 'recipeInstructions'})
        for element in pattern:
            step_number = element.findChildren("span", recursive=False)[0].get("id")
            step_description = element.find("span", {'itemprop': 'text'}).getText()

            step_image_path = "no_path"
            try:
                step_image_url = element.find("div", class_="emotion-1x955v4").findChildren(
                    "picture", recursive=False)[0].findChildren("img", recursive=False)[0].get("src")
                step_image_path = await save_image(recipe_name, step_image_url, headers)
            except AttributeError:
                logger.debug(f'{step_number} in recipe "{recipe_name}" does not have image')

            step = {
                step_number: {
                    "step_image_path": step_image_path,
                    "step_description": step_description.replace('\xa0', ' '),
                }
            }
            steps.append(step)

        recipe_page_info["steps"] = steps

        try:
            recipe_page_info["recipe_hint"] = soup.find("div", class_="emotion-1mtrnmn").text.strip()
        except AttributeError:
            recipe_page_info["recipe_hint"] = "no_recipe_hint"
            logger.debug(f'recipe "{recipe_name}" does not have recipe hint')

        await save_recipe_page_info(recipe_page_info)

        recipes_info.append(recipe_page_info)

        time.sleep(1)

    return recipes_info


async def get_recipes_urls(url: str, headers: dict, page: int) -> list:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{url}/recepty?page={page}", headers=headers) as response:
                soup = bs(await response.text(), "lxml")
                recipes_urls = soup.findAll("a", class_="emotion-18hxz5k")

                recipes_urls_list = []
                for recipe_url in recipes_urls:
                    recipes_urls_list.append(recipe_url.get("href"))
    except Exception as ex:
        logger.error(f"get recipes urls error: {ex}")
        return []
    return recipes_urls_list


async def main():
    logger.info("start parser")

    client = init_mongo_client()
    db = client.recipes_db
    collection = db.recipes

    page = 714
    while True:
        recipes_urls = await get_recipes_urls(URL, HEADERS, page)
        if len(recipes_urls) == 0:
            break
        page += 1

        recipes_info = await get_recipes_info(URL, recipes_urls, HEADERS)

        await save_recipes_info(collection, recipes_info)

        time.sleep(1)

    logger.info("stop parser")


if __name__ == '__main__':
    asyncio.run(main())
