/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("52p56pklkn98iqu");

  const categoryField = collection.schema.getFieldByName("category");
  if (categoryField) {
    categoryField.options.values = [
      "productivity",
      "creative",
      "gaming",
      "entertainment",
      "office",
      "other"
    ];
  }

  return dao.saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("52p56pklkn98iqu");

  const categoryField = collection.schema.getFieldByName("category");
  if (categoryField) {
    categoryField.options.values = [
      "productivity",
      "creative",
      "gaming",
      "office",
      "other"
    ];
  }

  return dao.saveCollection(collection);
})
