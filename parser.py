import time
import aiohttp
import asyncio
import aiofiles
from bs4 import BeautifulSoup as bs
import os

URL = "https://eda.ru"
HEADERS = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"}


async def save_image(recipe_name: str, step_image_url: str, headers: dict) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=step_image_url, headers=headers) as response:
                with aiofiles.open(f"images/{recipe_name}/" + "".join(step_image_url.split("/")[-3:]), 'wb') as image:
                    image.write(response)
    except Exception as ex:
        print(f"save image error: {ex}")

    return f"images/{recipe_name}/" + "".join(step_image_url.split("/")[-3:])


async def save_recipe_page_info(recipe_page_info: dict) -> None:
    try:
        with aiofiles.open(f"images/{recipe_page_info['recipe_name']}/{recipe_page_info['recipe_name']}.jsom" , 'wb') as file:
            file.write(recipe_page_info)
    except Exception as ex:
        print(f"save recipe page info error: {ex}")


async def get_recipe_page_info(url: str, recipes_urls: list, headers: dict) -> dict:
    for recipes_url in recipes_urls:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url=url + recipes_url, headers=headers) as response:
                    soup = bs(await response.text(), "lxml")

                    recipe_page_info = {
                        "recipe_name": soup.find("h1", class_="emotion-gl52ge").text.strip(),
                        "portions": soup.find("span", {'itemprop': 'recipeYield'}).getText(),
                        "cooking_time": soup.find("div", class_="emotion-my9yfq").text.strip(),
                        "description": soup.find("span", class_="emotion-1x1q7i2").text.strip().replace('\xa0', ' ')
                    }

                    os.mkdir(f"images/{recipe_page_info['recipe_name']}/")

                    ingredients = {}
                    ingredients_list = soup.findAll("span", {'itemprop': 'recipeIngredient'})
                    ingredients_weight_list = soup.findAll("span", class_="emotion-15im4d2")

                    for index, ingredient in enumerate(ingredients_list):
                        ingredients[ingredient.getText()] = ingredients_weight_list[index].getText()

                    recipe_page_info["ingredients"] = ingredients

                    nutritious = {
                        "calories": soup.find("span", {'itemprop': 'calories'}).text.strip(),
                        "proteinContent": soup.find("span", {'itemprop': 'proteinContent'}).text.strip(),
                        "fatContent": soup.find("span", {'itemprop': 'fatContent'}).text.strip(),
                        "carbohydrateContent": soup.find("span", {'itemprop': 'carbohydrateContent'}).text.strip()
                    }
                    recipe_page_info["nutritious"] = nutritious

                    steps = []
                    pattern = soup.findAll("div", {'itemprop': 'recipeInstructions'})
                    for element in pattern:
                        step_number = element.findChildren("span", recursive=False)[0].get("id")
                        step_image_url = element.find("div", class_="emotion-1x955v4").findChildren(
                            "picture", recursive=False)[0].findChildren("img", recursive=False)[0].get("src")
                        step_description = element.find("div", class_="emotion-19fjypw").find(
                            "span", {'itemprop': 'text'}).getText()

                        step_image_path = await save_image(recipe_page_info["recipe_name"], step_image_url, headers)

                        step = {
                            step_number: {
                                "step_image_path": step_image_path,
                                "step_description": step_description.replace('\xa0', ' '),
                            }
                        }
                        steps.append(step)

                    recipe_page_info["steps"] = steps

                    recipe_page_info["recipe_hint"] = soup.find("div", class_="emotion-1mtrnmn").text.strip()

                    await save_recipe_page_info(recipe_page_info)

                    return recipe_page_info

        except Exception as ex:
            print(f"get recipe page info error: {ex}")


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
        print(f"get recipes urls error: {ex}")
        return []
    return recipes_urls_list


async def main():
    page = 1
    while True:
        recipes_urls = await get_recipes_urls(URL, HEADERS, page)
        if len(recipes_urls) == 0:
            break
        page += 1

        recipe_page_info = await get_recipe_page_info(URL, recipes_urls, HEADERS)  # todo: add mongo driver

        time.sleep(1 / 10)


if __name__ == '__main__':
    asyncio.run(main())
