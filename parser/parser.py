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
import base64

load_dotenv()  # todo add pipenv

logging.basicConfig()
logger = logging.getLogger(__name__)
level = logging.getLevelName(os.getenv('LOGGING_LEVEL'))
logger.setLevel(level)

URL = "https://eda.ru"
HEADERS = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
}


def init_mongo_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    logger.debug(f"trying to init mongodb client")
    username = os.getenv('MONGO_INITDB_ROOT_USERNAME')
    password = os.getenv('MONGO_INITDB_ROOT_PASSWORD')
    host = os.getenv('MONGO_HOST')
    return motor.motor_asyncio.AsyncIOMotorClient(
        f"mongodb://{username}:{password}@{host}:27017/?authMechanism=DEFAULT")


async def save_recipes_info(collection: motor.motor_asyncio.core.AgnosticCollection, recipes_info: list) -> None:
    for recipe in recipes_info:
        logger.debug(f"trying to save recipe {recipe['recipe_name']} to mongodb")
        await collection.update_one({"_id": recipe["recipe_id"]}, {"$setOnInsert": recipe}, upsert=True)


async def get_image(recipe_name: str, image_url: str, headers: dict) -> bytes:
    logger.debug(f"trying to get recipe {recipe_name} image")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=image_url, headers=headers) as response:
                return await response.read()
    except Exception as ex:
        logger.error(f"get image error: {ex}")


async def get_recipes_info(recipes_urls: list) -> list:
    recipes_info = []
    for recipe_url in recipes_urls:
        logger.debug(f"trying to get recipe info by recipe url: {recipe_url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url=URL + recipe_url, headers=HEADERS) as response:
                    soup = bs(await response.text(), "lxml")

        except aiohttp.client.TooManyRedirects as ex:
            logger.debug(f"get recipe page info error: {ex}")

        except RuntimeError as ex:
            logger.debug(f"get recipe page info error: {ex}")

        try:
            recipe_name = soup.find("h1", class_="emotion-gl52ge").text.strip().replace('\xa0', ' ')
        except AttributeError:
            logger.debug(f"page {recipe_url} is broken")
            continue

        recipe_page_info = {
            "recipe_name": recipe_name,
            "portions": soup.find("span", {'itemprop': 'recipeYield'}).getText(),
            "cooking_time": soup.find("div", class_="emotion-my9yfq").text.strip()
        }

        recipe_id = soup.find("link", {'rel': 'canonical'}).get("href").split("-")[-1]
        recipe_page_info["recipe_id"] = recipe_id

        raw_tags = soup.find("div", class_="emotion-fq1t0q").findAll("li", {'itemprop': 'itemListElement'})
        tags = []
        for tag in raw_tags[1:]:
            tags.append(tag.getText())
        recipe_page_info["tags"] = tags

        image_bytes = ""
        try:
            preview_image_url = soup.find("span", {'itemprop': 'resultPhoto'}).get("content")
            image_bytes = await get_image(recipe_name, preview_image_url, HEADERS)

            if image_bytes != "" or image_bytes is not None:
                image_bytes = base64.b64encode(image_bytes).decode('utf-8')
        except AttributeError:
            logger.debug(f'recipe "{recipe_name}" does not have preview image')
        except TypeError:
            logger.debug(f'recipe "{recipe_name}" does not have preview image')

        recipe_page_info["preview_image"] = image_bytes

        try:
            recipe_page_info["description"] = soup.find("span", class_="emotion-aiknw3").text.strip().replace('\xa0', ' ')
        except AttributeError:
            recipe_page_info["description"] = "no_recipe_description"
            logger.debug(f'recipe "{recipe_name}" does not have description')

        ingredients = {}
        ingredients_list = soup.findAll("span", {'itemprop': 'recipeIngredient'})
        ingredients_weight_list = soup.findAll("span", class_="emotion-bsdd3p")

        for index, ingredient in enumerate(ingredients_list):
            ingredients[ingredient.getText()] = ingredients_weight_list[index].getText()
        recipe_page_info["ingredients"] = ingredients

        nutritious = {}
        try:
            nutritious["calories"] = soup.find("span", {'itemprop': 'calories'}).text.strip()
        except AttributeError:
            nutritious["calories"] = "0"
        try:
            nutritious["protein_content"] = soup.find("span", {'itemprop': 'proteinContent'}).text.strip()
        except AttributeError:
            nutritious["protein_content"] = "0"
        try:
            nutritious["fat_content"] = soup.find("span", {'itemprop': 'fatContent'}).text.strip()
        except AttributeError:
            nutritious["fat_content"] = "0"
        try:
            nutritious["carbohydrate_content"] = soup.find("span", {'itemprop': 'carbohydrateContent'}).text.strip()
        except AttributeError:
            nutritious["carbohydrate_content"] = "0"
        recipe_page_info["nutritious"] = nutritious

        steps = []
        pattern = soup.findAll("div", {'itemprop': 'recipeInstructions'})
        for element in pattern:
            step_number = element.findChildren("span", recursive=False)[0].get("id")
            step_description = element.find("span", {'itemprop': 'text'}).getText()

            image_bytes = ""
            try:
                step_image_url = element.find("div", class_="emotion-1x955v4").findChildren(
                    "picture", recursive=False)[0].findChildren("img", recursive=False)[0].get("src")
                if step_image_url is not None:
                    image_bytes = await get_image(recipe_name, step_image_url, HEADERS)

                if image_bytes != "" or image_bytes is not None:
                    image_bytes = base64.b64encode(image_bytes).decode('utf-8')
            except AttributeError:
                logger.debug(f'{step_number} in recipe "{recipe_name}" does not have image')
            except IndexError:
                logger.debug(f'{step_number} in recipe "{recipe_name}" does not have image')
            except TypeError:
                logger.debug(f'{step_number} in recipe "{recipe_name}" does not have image')

            step = {
                step_number: {
                    "step_image": image_bytes,
                    "step_description": step_description.replace('\xa0', ' ')
                }
            }
            steps.append(step)

        recipe_page_info["steps"] = steps

        try:
            recipe_page_info["recipe_hint"] = soup.find("div", class_="emotion-1mtrnmn").text.strip()
        except AttributeError:
            recipe_page_info["recipe_hint"] = "no_recipe_hint"
            logger.debug(f'recipe "{recipe_name}" does not have recipe hint')

        recipes_info.append(recipe_page_info)

        time.sleep(5)

    return recipes_info


async def get_recipes_urls(page: int) -> list:
    logger.debug(f"trying to get recipes urls from page: {page}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=f"{URL}/recepty?page={page}", headers=HEADERS) as response:
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
    logger.info("parser start")

    client = init_mongo_client()
    db = client.recipes_db
    collection = db.recipes

    page = 4
    while True:
        recipes_urls = await get_recipes_urls(page)
        if len(recipes_urls) == 0:
            break

        recipes_info = await get_recipes_info(recipes_urls)

        await save_recipes_info(collection, recipes_info)

        page += 1

        time.sleep(5)

    logger.info("parser stop")


if __name__ == '__main__':
    asyncio.run(main())
