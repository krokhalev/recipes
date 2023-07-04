import yaml
import asyncio
import motor.motor_asyncio
from dotenv import load_dotenv
import logging
import os
import uuid
import bson

load_dotenv()

logging.basicConfig()
logger = logging.getLogger(__name__)
level = logging.getLevelName(os.getenv('LOGGING_LEVEL'))
logger.setLevel(level)


def init_mongo_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    logger.debug(f"trying to init mongodb client")
    username = os.getenv('MONGO_INITDB_ROOT_USERNAME')
    password = os.getenv('MONGO_INITDB_ROOT_PASSWORD')
    host = os.getenv('MONGO_HOST')
    return motor.motor_asyncio.AsyncIOMotorClient(f"mongodb://{username}:{password}@{host}:27017/?authMechanism=DEFAULT")


async def get_documents_from_collection(collection, batch_size, mutated_count, projection):
    total_pages = mutated_count // batch_size
    residue_docs = mutated_count % batch_size

    documents = []

    if total_pages == 0:
        batch = collection.find({}, projection).limit(residue_docs)
        page_documents = await batch.to_list(length=residue_docs)
        documents.extend(page_documents)

    else:
        for page in range(total_pages):
            batch = collection.find({}, projection).skip(page * batch_size).limit(batch_size)
            page_documents = await batch.to_list(length=batch_size)
            documents.extend(page_documents)

            if page == total_pages:
                batch = collection.find({}, projection).skip(page * batch_size + 1).limit(residue_docs)
                page_documents = await batch.to_list(length=residue_docs)
                documents.extend(page_documents)

    return documents


async def save_mutated_info(collection: motor.motor_asyncio.core.AgnosticCollection, recipes_info: list) -> None:
    logger.debug(f"trying to save mutated recipes to mongodb")
    for recipe in recipes_info:
        await collection.insert_one(recipe)
    logger.debug(f"successful saved mutated recipes to mongodb")


async def main():
    conf = yaml.load(open('mapping.yaml'), Loader=yaml.Loader)
    recipe_struct = conf["recipe"]

    client = init_mongo_client()
    db = client.recipes_db
    collection = db.recipes
    mutated_collection = db.mutated
    mutated_collection.drop()

    batch_size = 20

    projection = {}

    for key, fields in recipe_struct.items():
        if fields["include_to_res"]:
            projection[key] = 1

    recipes = await get_documents_from_collection(collection, batch_size, conf["mutated_count"], projection)

    mutated_recipes = []
    for recipe in recipes:
        mutated_recipe = {}
        for res_key, res_val in recipe.items():
            # id section
            if res_key == "_id":
                if recipe_struct["_id"]["mutate_to_type"] == "uuid":
                    mutated_recipe["_id"] = bson.Binary.from_uuid(uuid.uuid4())

            # nutritious section
            if res_key == "nutritious":
                updated_nut_name = recipe_struct["nutritious"]["name_after_mutate"]
                mutated_recipe[updated_nut_name] = res_val

                for relation_field_key, relation_field_val in recipe_struct["nutritious"]["relation_fields"].items():
                    mutated_recipe[updated_nut_name][relation_field_val["name_after_mutate"]] = mutated_recipe[updated_nut_name].pop(relation_field_key)

                    new_content_type = recipe_struct["nutritious"]["relation_fields"][relation_field_key]["mutate_to_type"]
                    if new_content_type == "int":
                        old_content_type = mutated_recipe[updated_nut_name][relation_field_val["name_after_mutate"]]
                        mutated_recipe[updated_nut_name][relation_field_val["name_after_mutate"]] = int(old_content_type)

            # recipe name section
            if res_key == "recipe_name":
                mutated_recipe[recipe_struct["recipe_name"]["name_after_mutate"]] = res_val

        mutated_recipes.append(mutated_recipe)

    await save_mutated_info(mutated_collection, mutated_recipes)


if __name__ == '__main__':
    asyncio.run(main())
