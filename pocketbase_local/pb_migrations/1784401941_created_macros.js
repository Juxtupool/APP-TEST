/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const collection = new Collection({
    "id": "a5ccdyp61pcjcxu",
    "created": "2026-07-18 19:12:21.517Z",
    "updated": "2026-07-18 19:12:21.517Z",
    "name": "macros",
    "type": "base",
    "system": false,
    "schema": [
      {
        "system": false,
        "id": "mgyfdewr",
        "name": "name",
        "type": "text",
        "required": true,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      },
      {
        "system": false,
        "id": "3trnnik3",
        "name": "author",
        "type": "text",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      },
      {
        "system": false,
        "id": "prw0tvoa",
        "name": "description",
        "type": "text",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      },
      {
        "system": false,
        "id": "4vqexquo",
        "name": "category",
        "type": "select",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSelect": 1,
          "values": [
            "productivity",
            "creative",
            "gaming",
            "office",
            "other"
          ]
        }
      },
      {
        "system": false,
        "id": "mzrva8iv",
        "name": "tags",
        "type": "json",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSize": 5242880
        }
      },
      {
        "system": false,
        "id": "5aglojhz",
        "name": "type",
        "type": "select",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSelect": 1,
          "values": [
            "macro",
            "profile"
          ]
        }
      },
      {
        "system": false,
        "id": "2pk17vj9",
        "name": "macro_data",
        "type": "json",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSize": 5242880
        }
      },
      {
        "system": false,
        "id": "utrg0fis",
        "name": "profile_data",
        "type": "json",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSize": 5242880
        }
      },
      {
        "system": false,
        "id": "xrb6cfqb",
        "name": "likes",
        "type": "number",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": 0,
          "max": null,
          "noDecimal": true
        }
      },
      {
        "system": false,
        "id": "y1t8xgcw",
        "name": "downloads",
        "type": "number",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": 0,
          "max": null,
          "noDecimal": true
        }
      },
      {
        "system": false,
        "id": "x5oczjkt",
        "name": "approved",
        "type": "bool",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {}
      }
    ],
    "indexes": [],
    "listRule": "approved = true",
    "viewRule": "approved = true",
    "createRule": "",
    "updateRule": null,
    "deleteRule": null,
    "options": {}
  });

  return Dao(db).saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("a5ccdyp61pcjcxu");

  return dao.deleteCollection(collection);
})
